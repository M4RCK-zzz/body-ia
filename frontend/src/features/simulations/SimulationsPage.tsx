import "@/components/ui/forms.css";
import { useMySimulations } from "./hooks/useSimulations";
import { ScenarioBanner } from "./components/ScenarioBanner";
import { ScenarioList } from "./components/ScenarioList";
import "./simulations.css";

export function SimulationsPage() {
  const simulations = useMySimulations();

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <h1>Simulador de escenarios</h1>
          <p className="bv-muted">
            Explora "¿y si…?" sobre tus expedientes. Elige un expediente para crear un escenario
            o consulta los ya calculados.
          </p>
        </div>
      </header>

      <ScenarioBanner />

      {simulations.isLoading ? <p className="bv-muted">Cargando escenarios…</p> : null}
      {simulations.error ? (
        <p className="bv-alert bv-alert--error">{simulations.error.message}</p>
      ) : null}

      {simulations.data ? (
        <section className="bv-panel">
          <h2>Mis escenarios</h2>
          <ScenarioList simulations={simulations.data.items} />
        </section>
      ) : null}

      <p className="scenario-hint">
        Abre un expediente y usa "Simulador" en su ficha para crear un escenario sobre sus
        mediciones vigentes.
      </p>
    </div>
  );
}
