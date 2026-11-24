import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import "@/components/ui/forms.css";
import { DataKindBadge } from "@/components/ui/DataKindBadge";
import { useConsentStatuses } from "@/features/consent/hooks/useConsent";
import { useProfile } from "@/features/profiles/hooks/useProfiles";
import type { SimulationCreatePayload } from "@/types/simulation";
import { ScenarioBanner } from "./components/ScenarioBanner";
import { ScenarioComparator } from "./components/ScenarioComparator";
import { ScenarioForm } from "./components/ScenarioForm";
import { ScenarioList } from "./components/ScenarioList";
import {
  useArchiveSimulation,
  useCreateSimulation,
  useProfileSimulations,
  useSimulationComparison,
  useSimulationLimits,
} from "./hooks/useSimulations";
import "./simulations.css";

export function SimulationWorkspacePage() {
  const { profileId = "" } = useParams();
  const profile = useProfile(profileId);
  const consent = useConsentStatuses(profileId);
  const limits = useSimulationLimits();
  const list = useProfileSimulations(profileId);
  const create = useCreateSimulation(profileId);
  const archive = useArchiveSimulation();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const comparison = useSimulationComparison(selectedId ?? "", Boolean(selectedId));

  if (profile.error) {
    return (
      <div className="bv-page">
        <p className="bv-alert bv-alert--error">{profile.error.message}</p>
        <Link to="/expedientes">← Volver a Expedientes</Link>
      </div>
    );
  }

  const p = profile.data;
  const canWrite = p !== undefined && p.my_access !== "viewer";
  const consentValid = consent.data?.every((status) => status.valid) ?? false;

  let blockedReason: string | undefined;
  if (p && p.status !== "active") {
    blockedReason = "El expediente no está activo: no admite escenarios nuevos.";
  } else if (p && !canWrite) {
    blockedReason = "Tienes acceso de lector: puedes ver escenarios, pero no crearlos.";
  } else if (consent.data && !consentValid) {
    blockedReason = "Falta el consentimiento vigente: no se pueden crear escenarios.";
  }

  const submit = (payload: SimulationCreatePayload) =>
    create.mutate(payload, { onSuccess: (simulation) => setSelectedId(simulation.id) });

  return (
    <div className="bv-page">
      <header className="bv-page__header">
        <div>
          <Link to={`/expedientes/${profileId}`} className="bv-muted">
            ← Volver al expediente
          </Link>
          <h1>Simulador {p ? `· ${p.display_code}` : ""}</h1>
          <div className="scenario-header__badges">
            <DataKindBadge kind="simulation" />
            {limits.data ? (
              <span className="bv-muted">
                motor {limits.data.engine.name} {limits.data.engine.version} · tope{" "}
                {limits.data.max_delta_percent}% por métrica
              </span>
            ) : null}
          </div>
        </div>
      </header>

      <ScenarioBanner />

      {limits.isLoading ? <p className="bv-muted">Cargando contrato del motor…</p> : null}
      {limits.error ? <p className="bv-alert bv-alert--error">{limits.error.message}</p> : null}

      {limits.data ? (
        <ScenarioForm
          limits={limits.data}
          disabled={blockedReason !== undefined}
          disabledReason={blockedReason}
          submitting={create.isPending}
          onSubmit={submit}
        />
      ) : null}

      {create.error ? <p className="bv-alert bv-alert--error">{create.error.message}</p> : null}
      {create.data ? (
        <p className="bv-alert bv-alert--info" role="status">
          Escenario «{create.data.label}» registrado ({create.data.status}). Un worker lo calcula en
          segundo plano; esta página se actualiza sola.
        </p>
      ) : null}

      <section className="bv-panel">
        <h2>Escenarios del expediente</h2>
        {list.isLoading ? <p className="bv-muted">Cargando…</p> : null}
        {list.error ? <p className="bv-alert bv-alert--error">{list.error.message}</p> : null}
        {list.data ? (
          <ScenarioList
            simulations={list.data.items}
            onArchive={canWrite ? (simulation) => archive.mutate(simulation.id) : undefined}
            archivingId={archive.isPending ? (archive.variables ?? null) : null}
          />
        ) : null}
        {archive.error ? <p className="bv-alert bv-alert--error">{archive.error.message}</p> : null}
      </section>

      {list.data && list.data.items.length > 0 && !selectedId ? (
        <section className="bv-panel">
          <h2>Ver comparador</h2>
          <div className="bv-tabs" role="group" aria-label="Elegir escenario">
            {list.data.items
              .filter((simulation) => simulation.status === "completed")
              .map((simulation) => (
                <button
                  key={simulation.id}
                  type="button"
                  className="bv-tab"
                  onClick={() => setSelectedId(simulation.id)}
                >
                  {simulation.label}
                </button>
              ))}
          </div>
          <p className="bv-muted">
            Elegir un escenario calculado muestra la base observada frente al resultado hipotético.
          </p>
        </section>
      ) : null}

      {selectedId ? (
        <>
          {comparison.isLoading ? <p className="bv-muted">Cargando comparador…</p> : null}
          {comparison.error ? (
            <p className="bv-alert bv-alert--error">{comparison.error.message}</p>
          ) : null}
          {comparison.data ? (
            <>
              <ScenarioComparator comparison={comparison.data} />
              <p className="bv-row">
                <Link to={`/simulations/${profileId}/${selectedId}`} className="bv-btn bv-btn--small">
                  Abrir detalle del escenario
                </Link>
                <button
                  type="button"
                  className="bv-btn bv-btn--small"
                  onClick={() => setSelectedId(null)}
                >
                  Cerrar comparador
                </button>
              </p>
            </>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
