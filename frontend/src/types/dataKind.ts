export type DataKind =
  | 'observed'
  | 'visual_estimate'
  | 'approximate_reconstruction'
  | 'simulation'

export const DATA_KIND_META: Record<DataKind, { label: string; description: string }> = {
  observed: {
    label: 'MEDICIÓN OBSERVADA',
    description: 'Dato introducido o medido directamente: valor, unidad, fecha, método y responsable.',
  },
  visual_estimate: {
    label: 'ESTIMACIÓN',
    description: 'Inferencia algorítmica a partir de una imagen. No es una medida clínica.',
  },
  approximate_reconstruction: {
    label: 'RECONSTRUCCIÓN APROXIMADA',
    description: 'Geometría 3D aproximada. No es un gemelo digital anatómico validado.',
  },
  simulation: {
    label: 'ESCENARIO HIPOTÉTICO',
    description: 'Simulación con parámetros modificados. Nunca describe el cuerpo real.',
  },
}