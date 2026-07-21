import { describe, expect, test } from "vitest";
import { parseLicenseBarcode } from "./licenseScan";

const SAMPLE = `@
\x1e
ANSI 636001070002DL00410392ZN04330047DLDCANONE
DCBNONE
DCDNONE
DBA08312030
DCSCARTER
DACMAYA
DADLEE
DBD08312025
DBB01011980
DBC2
DAYBRO
DAU064 in
DAG100 HARBOR ROAD
DAIBALTIMORE
DAJMD
DAK212010000
DAQMD-D12345
DCFNONE
DCGUSA
DDEN
DDFN
DDGN
`;

describe("AAMVA license parsing", () => {
  test("maps a PDF417 payload into editable verification fields", () => {
    expect(parseLicenseBarcode(SAMPLE)).toEqual({
      fullName: "MAYA LEE CARTER",
      dateOfBirth: "1980-01-01",
      addressLine1: "100 HARBOR ROAD",
      city: "BALTIMORE",
      region: "MD",
      postalCode: "212010000",
      country: "US",
      documentNumber: "MD-D12345",
      issuingJurisdiction: "MD",
      documentExpiration: "2030-08-31",
    });
  });

  test("rejects malformed and oversized scanner input", () => {
    expect(() => parseLicenseBarcode("not a license")).toThrow(/not a supported/i);
    expect(() => parseLicenseBarcode(`ANSI${"A".repeat(20_001)}`)).toThrow(/not a supported/i);
  });
});
