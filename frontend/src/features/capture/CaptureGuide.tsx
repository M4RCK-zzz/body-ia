import { useState } from "react";

const GUIDE_CHECKS = [
  "Postura erguida, cuerpo completo visible dentro de la imagen",
  "Iluminación uniforme (ventana amplia, sin contraluz fuerte ni sombras duras)",
  "Fondo liso y sin distracciones; ni reflejos ni superficies espejo",
  "Vista frontal clara, sin oclusiones de las zonas relevantes",
  "Sin accesorios que oculten la zona a registrar (brazos, cadera, etc.)",
];

export function CaptureGuide() {
  const [checked, setChecked] = useState<Set<number>>(new Set());

  function toggle(index: number) {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  const complete = checked.size === GUIDE_CHECKS.length;

  return (
    <section className="bv-panel capture-guide" aria-labelledby="capture-guide-title">
      <h2 id="capture-guide-title">Guía de encuadre <span className="bv-tag bv-tag--observed">MATERIAL DE REFERENCIA</span></h2>
      <p className="bv-muted">
        Antes de subir la fotografía, comprueba cada punto. La guía orienta tu postura; no valida
        calidad automáticamente. Las fotos son material de referencia: nunca se convierten en
        mediciones ni reemplazan la cinta o la báscula.
      </p>
      <ul className="capture-guide__checks">
        {GUIDE_CHECKS.map((text, index) => (
          <li key={index}>
            <label className="capture-guide__check">
              <input
                type="checkbox"
                checked={checked.has(index)}
                onChange={() => toggle(index)}
              />
              <span>{text}</span>
            </label>
          </li>
        ))}
      </ul>
      <p className={`capture-guide__status ${complete ? "is-complete" : ""}`}>
        {complete
          ? "✓ Lista para subir. El sistema valida el contenido del archivo, no la pose."
          : `${checked.size}/${GUIDE_CHECKS.length} puntos revisados`}
      </p>
    </section>
  );
}
