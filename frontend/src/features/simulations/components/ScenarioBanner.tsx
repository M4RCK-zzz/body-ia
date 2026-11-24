import { DataKindBadge } from "@/components/ui/DataKindBadge";

/**
 * Aviso permanente de escenario hipotético. Se monta en todas las vistas de
 * simulación (lista, workspace y detalle), nunca es descartable.
 */
export function ScenarioBanner({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`scenario-banner${compact ? " scenario-banner--compact" : ""}`}
      role="note"
      aria-label="Advertencia de escenario hipotético"
    >
      <DataKindBadge kind="simulation" />
      <p>
        <strong>ESCENARIO HIPOTÉTICO.</strong> No describe el cuerpo real, no es una predicción y
        no modifica tus mediciones observadas. Las cifras salen de aritmética determinista sobre
        una copia de mediciones ya registradas.
      </p>
    </div>
  );
}
