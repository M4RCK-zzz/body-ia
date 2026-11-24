import { useMemo, useState } from "react";
import { RoleTags } from "@/features/admin/RoleTags";
import { HttpError } from "@/services/api/apiClient";
import { formatDate, formatDateTime } from "@/features/measurements/format";
import { ROLE_LABELS } from "@/features/auth/roles";
import { useAuth } from "@/features/auth/useAuth";
import type { RoleName, User } from "@/types/auth";
import { ROLE_ORDER } from "@/types/admin";
import { useAdminUsers, useSetRoles, useSetUserActive } from "../hooks/useAdmin";
import { Pagination } from "./Pagination";
import { RolesDialog } from "./RolesDialog";

const PAGE_SIZE = 20;

const EMPTY: User[] = [];

export function UsersTab() {
  const { user: me } = useAuth();
  const [search, setSearch] = useState("");
  const [role, setRole] = useState<RoleName | "">("");
  const [active, setActive] = useState<"all" | "active" | "inactive">("all");
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState<User | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const filters = useMemo(
    () => ({
      search: search.trim() || undefined,
      role: role || undefined,
      isActive: active === "all" ? undefined : active === "active",
    }),
    [search, role, active],
  );

  const query = useAdminUsers(filters, { limit: PAGE_SIZE, offset });
  const changeActive = useSetUserActive();
  const setRoles = useSetRoles();

  // Cualquier cambio de filtro invalida el offset: si no, se vería una página vacía.
  const resetPage = () => setOffset(0);

  const actionError = changeActive.error ?? setRoles.error;
  const actionErrorText =
    actionError instanceof HttpError || actionError instanceof Error ? actionError.message : null;

  const toggleActive = (row: User) => {
    setNotice(null);
    setRoles.reset();
    changeActive.reset();
    changeActive.mutate(
      { userId: row.id, active: !row.is_active },
      {
        onSuccess: (updated: User) =>
          setNotice(
            updated.is_active
              ? `${updated.full_name} puede volver a iniciar sesión.`
              : `${updated.full_name} ya no puede iniciar sesión.`,
          ),
      },
    );
  };

  return (
    <div className="admin-tab">
      <section className="bv-panel" aria-labelledby="admin-users-title">
        <h2 id="admin-users-title">Usuarios</h2>
        <p className="bv-muted">
          Cuentas registradas en esta instalación. Activar o desactivar una cuenta y cambiar sus
          roles queda registrado en la auditoría.
        </p>

        <form
          className="bv-row admin-filters"
          onSubmit={(event) => {
            event.preventDefault();
            resetPage();
          }}
        >
          <div className="bv-field admin-filters__search">
            <label htmlFor="admin-user-search">Buscar</label>
            <input
              id="admin-user-search"
              className="bv-input"
              type="search"
              placeholder="Nombre o correo"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                resetPage();
              }}
            />
          </div>
          <div className="bv-field">
            <label htmlFor="admin-user-role">Rol</label>
            <select
              id="admin-user-role"
              className="bv-input"
              value={role}
              onChange={(event) => {
                setRole(event.target.value as RoleName | "");
                resetPage();
              }}
            >
              <option value="">Todos</option>
              {ROLE_ORDER.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </div>
          <div className="bv-field">
            <label htmlFor="admin-user-state">Estado</label>
            <select
              id="admin-user-state"
              className="bv-input"
              value={active}
              onChange={(event) => {
                setActive(event.target.value as "all" | "active" | "inactive");
                resetPage();
              }}
            >
              <option value="all">Todas</option>
              <option value="active">Activas</option>
              <option value="inactive">Desactivadas</option>
            </select>
          </div>
          <button type="submit" className="bv-btn">
            Aplicar
          </button>
        </form>

        {notice ? (
          <p className="bv-alert bv-alert--info" role="status">
            {notice}
          </p>
        ) : null}
        {actionErrorText ? (
          <p className="bv-alert bv-alert--error" role="alert">
            {actionErrorText}
          </p>
        ) : null}
        {query.error ? (
          <p className="bv-alert bv-alert--error" role="alert">
            {query.error.message}
          </p>
        ) : null}
        {query.isLoading ? <p className="bv-muted">Cargando usuarios…</p> : null}

        {query.data ? (
          <>
            <div className="admin-table-scroll">
              <table className="bv-table">
                <caption className="bv-sr-only">
                  Usuarios: nombre, correo, roles, estado y fecha de alta
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Nombre</th>
                    <th scope="col">Correo</th>
                    <th scope="col">Roles</th>
                    <th scope="col">Estado</th>
                    <th scope="col">Alta</th>
                    <th scope="col">Último acceso</th>
                    <th scope="col">
                      <span className="bv-sr-only">Acciones</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(query.data.items.length === 0 ? EMPTY : query.data.items).map((row) => {
                    const isSelf = row.id === me?.id;
                    const pending = changeActive.isPending || setRoles.isPending;
                    return (
                      <tr key={row.id} className={row.is_active ? undefined : "is-inactive"}>
                        <th scope="row" className="admin-cell-name">
                          {row.full_name}
                          {isSelf ? <span className="admin-you">Tú</span> : null}
                        </th>
                        <td className="admin-cell-email">{row.email}</td>
                        <td>
                          <RoleTags roles={row.roles} />
                        </td>
                        <td>
                          <span className={`badge ${row.is_active ? "badge--ok" : "badge--neutral"}`}>
                            {row.is_active ? "Activa" : "Desactivada"}
                          </span>
                        </td>
                        <td>{formatDate(row.created_at)}</td>
                        <td>{row.last_login_at ? formatDateTime(row.last_login_at) : "—"}</td>
                        <td>
                          <div className="bv-actions">
                            <button
                              type="button"
                              className="bv-btn bv-btn--small"
                              onClick={() => {
                                setNotice(null);
                                changeActive.reset();
                                setEditing(row);
                              }}
                              disabled={pending}
                            >
                              Roles
                            </button>
                            <button
                              type="button"
                              className={`bv-btn bv-btn--small${row.is_active ? " bv-btn--danger" : ""}`}
                              onClick={() => toggleActive(row)}
                              disabled={pending || isSelf}
                              title={
                                isSelf
                                  ? "No puedes desactivar tu propia cuenta."
                                  : undefined
                              }
                            >
                              {row.is_active ? "Desactivar" : "Activar"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {query.data.items.length === 0 ? (
              <p className="bv-muted">
                Ningún usuario coincide con los filtros. Prueba con otro nombre, rol o estado.
              </p>
            ) : null}

            <Pagination
              total={query.data.total}
              limit={query.data.limit}
              offset={query.data.offset}
              onChange={setOffset}
              noun="usuarios"
              disabled={query.isFetching}
            />
          </>
        ) : null}
      </section>

      {editing ? (
        <RolesDialog
          user={editing}
          isSelf={editing.id === me?.id}
          submitting={setRoles.isPending}
          error={setRoles.error}
          onClose={() => {
            setRoles.reset();
            setEditing(null);
          }}
          onSubmit={(roles) => {
            setRoles.mutate(
              { userId: editing.id, roles },
              {
                onSuccess: (updated) => {
                  setEditing(null);
                  setRoles.reset();
                  setNotice(`Roles de ${updated.full_name} actualizados.`);
                },
              },
            );
          }}
        />
      ) : null}
    </div>
  );
}
