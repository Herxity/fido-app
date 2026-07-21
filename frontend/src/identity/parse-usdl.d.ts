declare module "parse-usdl" {
  export function parse(
    value: string,
    options?: { suppressErrors?: boolean },
  ): Record<string, unknown>;
}
