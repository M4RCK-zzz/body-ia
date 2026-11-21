import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { accessApi } from "../../services/api/access";
import { ACCESS_LABELS, type GrantableLevel } from "../../types/access";
import { AccessBadge } from "./AccessBadge";
import "./access.css";

export function AccessPanel({ profileId }: { profileId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["profiles", profileId, "access"] as const;
  const [email, setEmail] = useState("");
  const [level, setLevel] = useState<GrantableLevel>("viewer");

  const list = useQuery({ queryKey, queryFn: () => accessApi.list(profileId) });

  const grant = useMutation({
    mutationFn: () => accessApi.grant(profileId, { email: email.trim(), level }),
    onSuccess: async () => {
      setEmail("");
      await queryClient.invalidateQueries({ queryKey });
    },
  });

  const revoke = useMutation({
    mutationFn: (userId: string) => accessApi.revoke(profileId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey }),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (email.trim()) grant.mutate();
  }

  function onRevoke(userId: string, name: string) {
    if (window.confirm(`¿Quitar el acceso a ${name}? Surte efecto de inmediato.`)) {
      revoke.mutate(userId);
    }
  }

  return (
    <section className="access-panel" aria-labelledby="access-title">
      <h3 id="access-title">Quién tiene acceso</h3>
      <p>
        Solo el propietario concede o quita accesos. Para cambiar el nivel de
        alguien, concédele el nivel nuevo: queda constancia del anterior.
      </p>

      <form className="access-panel__form" onSubmit={onSubmit}>
        <label>
          Correo de la cuenta
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Nivel
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value as GrantableLevel)}
          >
            <option value="viewer">{ACCESS_LABELS.viewer} (solo ver)</option>
            <option value="editor">{ACCESS_LABELS.editor} (registrar y corregir)</option>
          </select>
        </label>
        <button type="submit" disabled={grant.isPending}>
          {grant.isPending ? "Concediendo…" : "Conceder acceso"}
        </button>
      </form>

      {grant.error && (
        <p role="alert" className="access-panel__error">{grant.error.message}</p>
      )}
      {revoke.error && (
        <p role="alert" className="access-panel__error">{revoke.error.message}</p>
      )}
      {list.isLoading && <p>Cargando accesos…</p>}
      {list.error && (
        <p role="alert" className="access-panel__error">{list.error.message}</p>
      )}

      {list.data && (
        <table>
          <thead>
            <tr>
              <th>Persona</th>
              <th>Correo</th>
              <th>Nivel</th>
              <th>Desde</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.data.map((entry) => (
              <tr key={entry.user_id}>
                <td>{entry.full_name}</td>
                <td>{entry.email}</td>
                <td><AccessBadge level={entry.level} /></td>
                <td>{new Date(entry.granted_at).toLocaleDateString("es-PE")}</td>
                <td>
                  {entry.level !== "owner" && (
                    <button
                      type="button"
                      disabled={revoke.isPending}
                      onClick={() => onRevoke(entry.user_id, entry.full_name)}
                    >
                      Quitar acceso
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
