const toSafeNumber = (value: number | string | null | undefined): number => {
  if (value === null || value === undefined || value === "") {
    return 0;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

export const formatCurrencyBRL = (
  value: number | string | null | undefined,
): string =>
  toSafeNumber(value).toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });

export const formatPercentBR = (
  value: number | string | null | undefined,
): string =>
  toSafeNumber(value).toLocaleString("pt-BR", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
