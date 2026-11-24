import { Suspense, lazy } from "react";

// El visor 3D arrastra three.js + drei: se carga en su propio chunk para no
// penalizar el arranque del resto de la aplicación.
const ViewerPage = lazy(() =>
  import("@/features/viewer3d/ViewerPage").then((module) => ({ default: module.ViewerPage })),
);

export function LazyViewer() {
  return (
    <Suspense fallback={<p className="bv-muted">Cargando visor 3D…</p>}>
      <ViewerPage />
    </Suspense>
  );
}
