# Procedencia y licencias de los modelos 3D

> Archivo generado por `frontend/scripts/build-anatomy-assets.mjs`. No editar a mano.
> Generado: 2026-11-24T03:46:52.916Z

## Obra original

- **Atlas de referencia:** [3d-human-body-anatomy](https://github.com/SeemaBansal1/3d-human-body-anatomy) (commit `2891243`), aplicación de visualización creada por Lluis Vinent sobre el atlas **Z-Anatomy**.
- **Geometría de base:** **BodyParts3D**, © The Database Center for Life Science (DBCLS), licencia **CC BY-SA 2.1 Japan**.
- **Z-Anatomy:** obra derivada distribuida bajo **CC BY-SA 4.0**.

## Licencia de estos archivos

Los `*.glb` de `frontend/public/models/` son **obras derivadas** del atlas anterior
(se eliminaron componentes y se reexportaron): se distribuyen bajo **Creative Commons
Atribución-CompartirIgual 4.0 Internacional (CC BY-SA 4.0)**.
Texto de la licencia: https://creativecommons.org/licenses/by-sa/4.0/legalcode.es

Debes mantener la atribución y compartir cualquier obra derivada bajo la misma licencia.

## Componentes eliminados antes de publicar

| Componente | Autor | Licencia | Acción |
| --- | --- | --- | --- |
| Riñón (`Kidney.l/r.001`, `Renal pelvis.l/r.001`) | Lissie Cowley | CC BY-NC 4.0 | **Eliminado** de `organs.glb` (prohibía el uso comercial) |
| Oído interno | Dundee | CC BY-NC-SA 4.0 | No se exportó a los GLB web; no hay geometry que eliminar (se documenta por transparencia) |

Los vasos renales y las glándulas suprarrenales pertenecen a BodyParts3D (CC BY-SA) y
se conservan.

## Capas incluidas

| Capa | Archivo | Meshes | Triángulos | Peso | SHA-256 (16) |
| --- | --- | --- | --- | --- | --- |
| Piel | `models/skin.glb` | 256 | 154.865 | 0.73 MB | `3dc1c812961c1945` |
| Esqueleto | `models/skeleton.glb` | 271 | 304.452 | 1.21 MB | `3cee480391401a70` |
| Músculos | `models/muscles.glb` | 476 | 447.787 | 1.87 MB | `c898c281b072007c` |
| Órganos | `models/organs.glb` | 293 | 387.717 | 1.51 MB | `70f2deb5e0a83578` |
| Arterias | `models/arteries.glb` | 417 | 408.542 | 1.67 MB | `e4f099ec88cbb448` |
| Venas | `models/veins.glb` | 226 | 305.651 | 1.13 MB | `14c3974fdbac0cb6` |
| Nervios | `models/nerves.glb` | 255 | 277.720 | 1.08 MB | `3225a154046d13cd` |

Total: **2194** mallas · **2.286.734** triángulos · **9.20 MB**.

## Decodificador Draco

`frontend/public/draco/` contiene el decodificador Draco de **three.js** (licencia MIT,
© Google Inc. y contribuidores), usado para descomprimir las mallas
(`KHR_draco_mesh_compression`).

## Límites de uso

Estos modelos son una **reconstrucción aproximada con fines educativos**. No son un
gemelo digital del paciente, no provienen de imágenes del expediente y **no sirven para
diagnóstico, medición ni decisión clínica** (ver ADR-007).
