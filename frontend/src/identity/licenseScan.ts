import { parse } from "parse-usdl";

export interface ParsedLicense {
  fullName: string;
  dateOfBirth: string;
  addressLine1: string;
  city: string;
  region: string;
  postalCode: string;
  country: string;
  documentNumber: string;
  issuingJurisdiction: string;
  documentExpiration: string;
}

const text = (value: unknown) => typeof value === "string" ? value.trim() : "";
const dateValue = (value: unknown) => {
  if (typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
  if (typeof value !== "number" || !Number.isFinite(value)) return "";
  return new Date(value).toISOString().slice(0, 10);
};

export function parseLicenseBarcode(raw: string): ParsedLicense {
  if (raw.length > 20_000 || !raw.includes("ANSI")) throw new Error("This is not a supported AAMVA license barcode.");
  const parsed = parse(raw, { suppressErrors: false });
  const fullName = [text(parsed.firstName), text(parsed.middleName), text(parsed.lastName)].filter(Boolean).join(" ");
  const state = text(parsed.addressState).toUpperCase();
  const issuer = text(parsed.issuer).toUpperCase();
  const result: ParsedLicense = {
    fullName,
    dateOfBirth: dateValue(parsed.dateOfBirth),
    addressLine1: text(parsed.addressStreet),
    city: text(parsed.addressCity),
    region: state,
    postalCode: text(parsed.addressPostalCode).slice(0, 10),
    country: issuer === "CAN" ? "CA" : "US",
    documentNumber: text(parsed.documentNumber),
    issuingJurisdiction: state,
    documentExpiration: dateValue(parsed.dateOfExpiry),
  };
  if (!result.fullName || !result.dateOfBirth || !result.documentNumber || !result.documentExpiration) {
    throw new Error("The barcode is missing required identity fields. Enter them manually.");
  }
  return result;
}
