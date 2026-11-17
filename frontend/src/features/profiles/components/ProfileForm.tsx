import { useState, type FormEvent } from "react";
import { FormField } from "@/components/ui/FormField";
import { useCreateProfile } from "../hooks/useProfiles";

const CODE_PATTERN = /^[A-Z0-9][A-Z0-9_-]{2,39}$/;

export function ProfileForm() {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const mutation = useCreateProfile();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const normalized = code.trim().toUpperCase();
    if (!CODE_PATTERN.test(normalized)) {
      setError("3 a 40 caracteres: letras, números, guion o guion bajo.");
      return;
    }
    setError(null);
    mutation.mutate(normalized, { onSuccess: () => setCode("") });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="bv-row">
      <FormField label="Código del expediente" htmlFor="p-code" error={error}
        hint="Usa un código seudónimo (p. ej. BV-001). No escribas nombres reales ni datos identificables.">
        <input id="p-code" className="bv-input" value={code} maxLength={40}
          onChange={(e) => setCode(e.target.value)} />
      </FormField>
      <button type="submit" className="bv-btn bv-btn--primary" disabled={mutation.isPending}>
        {mutation.isPending ? "Creando…" : "Crear expediente"}
      </button>
      {mutation.isError ? (
        <p className="bv-alert bv-alert--error" role="alert" style={{ flexBasis: "100%" }}>
          {mutation.error.message}
        </p>
      ) : null}
    </form>
  );
}