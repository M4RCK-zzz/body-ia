import { Suspense, useCallback, useEffect, useMemo, useRef, useState, type ComponentRef, type RefObject } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

/** Tipo del control de órbita sin depender del paquete transitivo `three-stdlib`. */
type OrbitControlsImpl = ComponentRef<typeof OrbitControls>

import {
  VIEWER_CAMERA_PRESETS,
  VIEWER_TARGET,
  type AnatomyLayerId,
  type AnatomyLayerManifest,
  type ViewerCameraPreset,
} from '@/types/viewer3d'
import { LayerModel } from './LayerModel'
import { ViewerErrorBoundary } from './ViewerErrorBoundary'

export interface ViewerLayerRuntime {
  manifest: AnatomyLayerManifest
  visible: boolean
  opacity: number
  /** La capa ya se pidió al menos una vez (streaming: no se descarga hasta encenderla). */
  mounted: boolean
}

interface BodyCanvasProps {
  layers: ViewerLayerRuntime[]
  wireframe: boolean
  autoRotate: boolean
  preset: ViewerCameraPreset
  /** En móvil se baja el DPR y se desactivan efectos caros. */
  lowPower: boolean
  onLayerReady: (layer: AnatomyLayerId, meshes: number) => void
  onLayerFailed: (layer: AnatomyLayerId, message: string) => void
  onContextLost: () => void
}

/** Cámara que viaja hacia el preset elegido y mantiene el encuadre del cuerpo. */
function CameraRig({
  preset,
  autoRotate,
  controlsRef,
}: {
  preset: ViewerCameraPreset
  autoRotate: boolean
  controlsRef: RefObject<OrbitControlsImpl | null>
}) {
  const camera = useThree((state) => state.camera)
  const goal = useMemo(() => new THREE.Vector3(), [])
  const animating = useRef(true)

  useEffect(() => {
    goal.set(...VIEWER_CAMERA_PRESETS[preset].position)
    animating.current = true
  }, [goal, preset])

  useEffect(() => {
    const controls = controlsRef.current
    if (controls) {
      controls.autoRotate = autoRotate
      controls.target.set(...VIEWER_TARGET)
      controls.update()
    }
  }, [autoRotate, controlsRef])

  useFrame((_, delta) => {
    if (!animating.current) return
    // Movimiento suave hacia el preset; el usuario puede interrumpirlo orbitando.
    const step = Math.min(1, delta * 6)
    camera.position.lerp(goal, step)
    if (camera.position.distanceTo(goal) < 0.01) {
      camera.position.copy(goal)
      animating.current = false
    }
    camera.lookAt(VIEWER_TARGET[0], VIEWER_TARGET[1], VIEWER_TARGET[2])
    controlsRef.current?.update()
  })

  return null
}

function SceneContent({
  layers,
  wireframe,
  autoRotate,
  preset,
  lowPower,
  onLayerReady,
  onLayerFailed,
}: Omit<BodyCanvasProps, 'onContextLost'>) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null)

  return (
    <>
      <ambientLight intensity={lowPower ? 0.85 : 0.6} />
      <hemisphereLight args={['#dfe9ff', '#0a1730', lowPower ? 1.0 : 0.7]} />
      <directionalLight position={[3, 5, 4]} intensity={lowPower ? 1.5 : 1.9} />
      <directionalLight position={[-3.5, 2.5, -4]} intensity={0.8} />
      <directionalLight position={[0, -2, 3]} intensity={0.25} />

      <CameraRig preset={preset} autoRotate={autoRotate} controlsRef={controlsRef} />
      <OrbitControls
        ref={controlsRef}
        makeDefault
        target={VIEWER_TARGET}
        enableDamping
        dampingFactor={0.08}
        minDistance={0.6}
        maxDistance={6}
        maxPolarAngle={Math.PI * 0.95}
        autoRotateSpeed={0.7}
        enablePan={!lowPower}
      />

      {layers
        .filter((layer) => layer.mounted)
        .map((layer) => (
          <ViewerErrorBoundary
            key={layer.manifest.id}
            label={layer.manifest.label.toLowerCase()}
            onError={(message) => onLayerFailed(layer.manifest.id, message)}
          >
            <Suspense fallback={null}>
              <LayerModel
                layer={layer.manifest}
                visible={layer.visible}
                opacity={layer.opacity}
                wireframe={wireframe}
                onReady={onLayerReady}
              />
            </Suspense>
          </ViewerErrorBoundary>
        ))}
    </>
  )
}

/**
 * Escucha la pérdida de contexto WebGL del canvas. `preventDefault()` permite
 * que el navegador pueda restaurarlo; aun así el visor pide un reinicio explícito
 * porque las geometrías y materiales ya subidos a la GPU se pierden.
 */
function useContextLossWatch(onContextLost: () => void): (element: HTMLCanvasElement | null) => void {
  const [canvasEl, setCanvasEl] = useState<HTMLCanvasElement | null>(null)

  useEffect(() => {
    if (!canvasEl) return
    const onLost = (event: Event) => {
      event.preventDefault()
      onContextLost()
    }
    canvasEl.addEventListener('webglcontextlost', onLost)
    return () => canvasEl.removeEventListener('webglcontextlost', onLost)
  }, [canvasEl, onContextLost])

  return useCallback((element: HTMLCanvasElement | null) => setCanvasEl(element), [])
}

export function BodyCanvas({
  layers,
  wireframe,
  autoRotate,
  preset,
  lowPower,
  onLayerReady,
  onLayerFailed,
  onContextLost,
}: BodyCanvasProps) {
  const registerCanvas = useContextLossWatch(onContextLost)
  const gl = useMemo(
    () => ({
      antialias: !lowPower,
      alpha: true,
      powerPreference: 'high-performance' as const,
      // En móvil, el renderer no debe intentar resoluciones 3x.
      failIfMajorPerformanceCaveat: false,
    }),
    [lowPower],
  )

  return (
    <Canvas
      className="viewer3d__canvas"
      dpr={lowPower ? [1, 1.25] : [1, 2]}
      shadows={false}
      gl={gl}
      camera={{ position: VIEWER_CAMERA_PRESETS.frontal.position, fov: 38, near: 0.01, far: 40 }}
      onCreated={({ gl: renderer, scene }) => {
        renderer.toneMapping = THREE.ACESFilmicToneMapping
        renderer.toneMappingExposure = 1.05
        scene.background = null
        registerCanvas(renderer.domElement)
      }}
    >
      <SceneContent
        layers={layers}
        wireframe={wireframe}
        autoRotate={autoRotate}
        preset={preset}
        lowPower={lowPower}
        onLayerReady={onLayerReady}
        onLayerFailed={onLayerFailed}
      />
    </Canvas>
  )
}
