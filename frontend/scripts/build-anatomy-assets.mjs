#!/usr/bin/env node
/**
 * build-anatomy-assets.mjs — Fase 6 (Visor 3D)
 *
 * Genera los activos 3D servidos por el visor a partir del atlas de referencia
 * `3d-human-body-anatomy` (Z-Anatomy / BodyParts3D, CC BY-SA 4.0).
 *
 * Pasos:
 *   1. Lee los 7 GLB originales de un directorio fuente (--source).
 *   2. Elimina los meshes CC BY-NC 4.0 (riñón de Lissie Cowley): los 4 nodos
 *      `Kidney.l.001`, `Kidney.r.001`, `Renal pelvis.l.001`, `Renal pelvis.r.001`
 *      de `organs.glb`. El resto de las capas se copia sin cambios.
 *   3. Escribe los GLB en `public/models/` conservando la compresión Draco.
 *   4. Calcula métricas reales (meshes, triángulos, bbox, sha256, bytes) y
 *      escribe `public/models/manifest.json` + `public/models/ATTRIBUTION.md`.
 *   5. Copia el decodificador Draco de three.js a `public/draco/`.
 *
 * Uso (desde `frontend/`):
 *   npm run assets:anatomy -- --source ../.tmp/3d-human-body-anatomy/web/public/models
 *
 * La fuente NO se versiona: se obtiene con
 *   git clone --depth 1 https://github.com/SeemaBansal1/3d-human-body-anatomy.git
 * (commit de referencia: 2891243)
 */
import { createHash } from 'node:crypto'
import { copyFile, mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { NodeIO } from '@gltf-transform/core'
import { ALL_EXTENSIONS } from '@gltf-transform/extensions'
import draco3d from 'draco3d'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND = path.resolve(HERE, '..')
const OUT_MODELS = path.join(FRONTEND, 'public', 'models')
const OUT_DRACO = path.join(FRONTEND, 'public', 'draco')

/** Nodos CC BY-NC 4.0 (riñón, Lissie Cowley) que hay que retirar antes de publicar. */
const NC_NODES = [
  'Kidney.l.001',
  'Kidney.r.001',
  'Renal pelvis.l.001',
  'Renal pelvis.r.001',
]

/** Capas del atlas: id lógico, archivo, etiqueta en español y color de render. */
const LAYERS = [
  { id: 'skin', file: 'skin.glb', label: 'Piel', color: '#f0c9b6', order: 7 },
  { id: 'skeleton', file: 'skeleton.glb', label: 'Esqueleto', color: '#e8e2d0', order: 1 },
  { id: 'muscles', file: 'muscles.glb', label: 'Músculos', color: '#c2564b', order: 2 },
  { id: 'organs', file: 'organs.glb', label: 'Órganos', color: '#8d6e63', order: 3 },
  { id: 'arteries', file: 'arteries.glb', label: 'Arterias', color: '#d0342c', order: 4 },
  { id: 'veins', file: 'veins.glb', label: 'Venas', color: '#3b6fd4', order: 5 },
  { id: 'nerves', file: 'nerves.glb', label: 'Nervios', color: '#e0b13a', order: 6 },
]

function parseArgs(argv) {
  const args = {}
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i]
    if (token.startsWith('--')) {
      const key = token.slice(2)
      const value = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : 'true'
      args[key] = value
    }
  }
  return args
}

const sha256 = (buffer) => createHash('sha256').update(buffer).digest('hex')
const round = (value) => Math.round(value * 10000) / 10000

async function createIO() {
  return new NodeIO()
    .registerExtensions(ALL_EXTENSIONS)
    .registerDependencies({
      'draco3d.decoder': await draco3d.createDecoderModule(),
      'draco3d.encoder': await draco3d.createEncoderModule(),
    })
}

/** Cuenta meshes/triángulos y calcula el bbox en espacio de mundo (nodos sin transform). */
function measure(document) {
  const root = document.getRoot()
  let meshes = 0
  let triangles = 0
  const min = [Infinity, Infinity, Infinity]
  const max = [-Infinity, -Infinity, -Infinity]

  for (const node of root.listNodes()) {
    if (node.getMesh()) meshes += 1
  }
  for (const mesh of root.listMeshes()) {
    for (const prim of mesh.listPrimitives()) {
      const indices = prim.getIndices()
      const position = prim.getAttribute('POSITION')
      if (indices) triangles += indices.getCount() / 3
      else if (position) triangles += position.getCount() / 3
      if (!position) continue
      for (let i = 0; i < position.getCount(); i += 1) {
        const x = position.getElement(i, [])
        for (let axis = 0; axis < 3; axis += 1) {
          if (x[axis] < min[axis]) min[axis] = x[axis]
          if (x[axis] > max[axis]) max[axis] = x[axis]
        }
      }
    }
  }

  return {
    meshes,
    triangles: Math.round(triangles),
    bbox: {
      min: min.map(round),
      max: max.map(round),
      size: [0, 1, 2].map((axis) => round(max[axis] - min[axis])),
    },
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const sourceDir = path.resolve(FRONTEND, args.source ?? '../.tmp/3d-human-body-anatomy/web/public/models')

  try {
    await stat(sourceDir)
  } catch {
    console.error(`[anatomy] No existe el directorio fuente: ${sourceDir}`)
    console.error('[anatomy] Clona el atlas y pasa --source <ruta>/web/public/models')
    process.exit(1)
  }

  await mkdir(OUT_MODELS, { recursive: true })
  await mkdir(OUT_DRACO, { recursive: true })

  const io = await createIO()
  const manifestLayers = []

  for (const layer of LAYERS) {
    const inputPath = path.join(sourceDir, layer.file)
    const outputPath = path.join(OUT_MODELS, layer.file)
    const document = await io.read(inputPath)
    const root = document.getRoot()

    const removed = []
    if (layer.id === 'organs') {
      for (const name of NC_NODES) {
        const nodes = root.listNodes().filter((node) => node.getName() === name)
        for (const node of nodes) {
          node.dispose()
          removed.push(name)
        }
      }
      const missing = NC_NODES.filter((name) => !removed.includes(name))
      if (missing.length > 0) {
        throw new Error(
          `[anatomy] No se encontraron los meshes NC esperados en ${layer.file}: ${missing.join(', ')}`,
        )
      }
      // Un mesh huérfano (sin nodo) seguiría exportándose: lo purgamos.
      for (const mesh of root.listMeshes()) {
        if (mesh.listParents().length === 1) mesh.dispose()
      }
    }

    const metrics = measure(document)
    await io.write(outputPath, document)

    const buffer = await readFile(outputPath)
    manifestLayers.push({
      id: layer.id,
      label: layer.label,
      file: `models/${layer.file}`,
      order: layer.order,
      color: layer.color,
      ...metrics,
      bytes: buffer.byteLength,
      sha256: sha256(buffer),
      pruned_nc_nodes: removed.sort(),
      license: 'CC BY-SA 4.0 (Z-Anatomy · BodyParts3D)',
    })

    console.log(
      `[anatomy] ${layer.file}: ${metrics.meshes} meshes · ${metrics.triangles} tris · ` +
        `${(buffer.byteLength / 1024 / 1024).toFixed(2)} MB` +
        (removed.length > 0 ? ` · ${removed.length} nodos NC podados` : ''),
    )
  }

  // Decodificador Draco: se toma de three.js (MIT) para no depender del CDN de Google.
  const dracoSource = path.join(FRONTEND, 'node_modules', 'three', 'examples', 'jsm', 'libs', 'draco', 'gltf')
  for (const file of await readdir(dracoSource)) {
    await copyFile(path.join(dracoSource, file), path.join(OUT_DRACO, file))
  }

  const totals = manifestLayers.reduce(
    (acc, layer) => ({
      meshes: acc.meshes + layer.meshes,
      triangles: acc.triangles + layer.triangles,
      bytes: acc.bytes + layer.bytes,
    }),
    { meshes: 0, triangles: 0, bytes: 0 },
  )

  const manifest = {
    schema_version: 1,
    kind: 'approximate_reconstruction',
    generated_at: new Date().toISOString(),
    source: {
      repository: 'https://github.com/SeemaBansal1/3d-human-body-anatomy',
      commit: '2891243',
      atlas: 'Z-Anatomy',
      upstream: 'BodyParts3D (DBCLS, CC BY-SA 2.1 JP)',
    },
    licenses: {
      model: 'CC BY-SA 4.0',
      upstream_model: 'CC BY-SA 2.1 JP',
      removed: ['Kidney (Lissie Cowley) CC BY-NC 4.0', 'Inner ear (Dundee) CC BY-NC-SA 4.0'],
      note:
        'Los componentes no comerciales (riñón) se eliminaron antes de publicar. ' +
        'El derivado se distribuye bajo CC BY-SA 4.0; ver ATTRIBUTION.md.',
    },
    units: 'metros',
    up_axis: 'Y',
    origin: 'pies (Y=0)',
    draco: {
      required: true,
      decoder_path: 'draco/',
      encoder: 'gltf-transform + draco3d',
    },
    totals,
    layers: manifestLayers,
  }

  await writeFile(path.join(OUT_MODELS, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`)

  const rows = manifestLayers
    .map(
      (layer) =>
        `| ${layer.label} | \`${layer.file}\` | ${layer.meshes} | ${layer.triangles.toLocaleString('es-ES')} | ${(layer.bytes / 1024 / 1024).toFixed(2)} MB | \`${layer.sha256.slice(0, 16)}\` |`,
    )
    .join('\n')

  const attribution = `# Procedencia y licencias de los modelos 3D

> Archivo generado por \`frontend/scripts/build-anatomy-assets.mjs\`. No editar a mano.
> Generado: ${manifest.generated_at}

## Obra original

- **Atlas de referencia:** [3d-human-body-anatomy](https://github.com/SeemaBansal1/3d-human-body-anatomy) (commit \`2891243\`), aplicación de visualización creada por Lluis Vinent sobre el atlas **Z-Anatomy**.
- **Geometría de base:** **BodyParts3D**, © The Database Center for Life Science (DBCLS), licencia **CC BY-SA 2.1 Japan**.
- **Z-Anatomy:** obra derivada distribuida bajo **CC BY-SA 4.0**.

## Licencia de estos archivos

Los \`*.glb\` de \`frontend/public/models/\` son **obras derivadas** del atlas anterior
(se eliminaron componentes y se reexportaron): se distribuyen bajo **Creative Commons
Atribución-CompartirIgual 4.0 Internacional (CC BY-SA 4.0)**.
Texto de la licencia: https://creativecommons.org/licenses/by-sa/4.0/legalcode.es

Debes mantener la atribución y compartir cualquier obra derivada bajo la misma licencia.

## Componentes eliminados antes de publicar

| Componente | Autor | Licencia | Acción |
| --- | --- | --- | --- |
| Riñón (\`Kidney.l/r.001\`, \`Renal pelvis.l/r.001\`) | Lissie Cowley | CC BY-NC 4.0 | **Eliminado** de \`organs.glb\` (prohibía el uso comercial) |
| Oído interno | Dundee | CC BY-NC-SA 4.0 | No se exportó a los GLB web; no hay geometry que eliminar (se documenta por transparencia) |

Los vasos renales y las glándulas suprarrenales pertenecen a BodyParts3D (CC BY-SA) y
se conservan.

## Capas incluidas

| Capa | Archivo | Meshes | Triángulos | Peso | SHA-256 (16) |
| --- | --- | --- | --- | --- | --- |
${rows}

Total: **${totals.meshes}** mallas · **${totals.triangles.toLocaleString('es-ES')}** triángulos · **${(totals.bytes / 1024 / 1024).toFixed(2)} MB**.

## Decodificador Draco

\`frontend/public/draco/\` contiene el decodificador Draco de **three.js** (licencia MIT,
© Google Inc. y contribuidores), usado para descomprimir las mallas
(\`KHR_draco_mesh_compression\`).

## Límites de uso

Estos modelos son una **reconstrucción aproximada con fines educativos**. No son un
gemelo digital del paciente, no provienen de imágenes del expediente y **no sirven para
diagnóstico, medición ni decisión clínica** (ver ADR-007).
`

  await writeFile(path.join(OUT_MODELS, 'ATTRIBUTION.md'), attribution)

  console.log(
    `[anatomy] Total: ${totals.meshes} meshes · ${totals.triangles} tris · ` +
      `${(totals.bytes / 1024 / 1024).toFixed(2)} MB`,
  )
  console.log('[anatomy] manifest.json y ATTRIBUTION.md escritos.')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
