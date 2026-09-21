/** Presentation only, no floating-point conversion of approved measurements. */
export function formatTarget(value: string, unit: string): string {
  const match=/^(-?)([0-9]+)\.([0-9]{2})$/.exec(value);
  if (!match) return `${value} ${unit}`;
  const whole=match[2].replace(/\B(?=(\d{3})+(?!\d))/g," ");
  const fraction=match[3]==="00"?"":","+match[3].replace(/0$/,"");
  return `${match[1]}${whole}${fraction} ${unit==="count"?"шт.":unit==="RUB"?"₽":unit}`;
}
