import { ACCESS_LABELS, type AccessLevel } from "../../types/access";
import "./access.css";

export function AccessBadge({ level }: { level: AccessLevel }) {
  return (
    <span className={`access-badge access-badge--${level}`}>
      {ACCESS_LABELS[level]}
    </span>
  );
}
