import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MeasurementCatalog, MeasurementSeries, MetricSpec } from "@/types/measurement";
import { formatDate, formatDateTime, formatValue, methodLabel } from "../format";

interface ChartPoint {
  t: number;
  value: number;
  corrected: boolean;
  method: string;
}

interface DotProps {
  cx?: number;
  cy?: number;
  payload?: ChartPoint;
}

function PointDot({ cx, cy, payload }: DotProps) {
  if (cx === undefined || cy === undefined) return null;
  return (
    <circle cx={cx} cy={cy} r={4.5} fill={payload?.corrected ? "#8b5cf6" : "#22d3ee"}
      stroke="#0b1220" strokeWidth={1.5} />
  );
}

interface TooltipProps {
  active?: boolean;
  payload?: { payload: ChartPoint }[];
  spec: MetricSpec;
  catalog: MeasurementCatalog;
}

function ChartTooltip({ active, payload, spec, catalog }: TooltipProps) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="bv-panel" style={{ padding: "0.5rem 0.75rem", fontSize: "0.8rem" }}>
      <div>{formatDateTime(point.t)}</div>
      <strong>{formatValue(point.value, spec.unit)}</strong>
      <div className="bv-muted">
        {methodLabel(catalog, point.method as never)}
        {point.corrected ? " · versión corregida" : ""}
      </div>
    </div>
  );
}

interface Props {
  series: MeasurementSeries;
  spec: MetricSpec;
  catalog: MeasurementCatalog;
}

export function MetricChart({ series, spec, catalog }: Props) {
  const data: ChartPoint[] = series.points.map((p) => ({
    t: Date.parse(p.measured_at),
    value: p.value,
    corrected: p.corrected,
    method: p.method,
  }));

  if (data.length === 0) {
    return <p className="bv-muted">Sin datos para graficar. Registra la primera medición.</p>;
  }

  return (
    <figure style={{ margin: 0 }} aria-label={`Evolución real de ${spec.label}`}>
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
            <CartesianGrid stroke="#1f2f52" strokeDasharray="3 3" />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]}
              tickFormatter={(t: number) => formatDate(t)} stroke="#8fa3c4"
              padding={{ left: 16, right: 16 }} />
            <YAxis stroke="#8fa3c4" width={56} unit={` ${spec.unit}`}
              domain={[(min: number) => Math.floor(min - 1), (max: number) => Math.ceil(max + 1)]} />
            <Tooltip content={<ChartTooltip spec={spec} catalog={catalog} />} />
            <Line type="monotone" dataKey="value" stroke="#22d3ee" strokeWidth={2}
              dot={<PointDot />} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="bv-legend">
        <span><i style={{ background: "#22d3ee" }} />Medición original</span>
        <span><i style={{ background: "#8b5cf6" }} />Valor corregido (versión vigente)</span>
      </figcaption>
    </figure>
  );
}