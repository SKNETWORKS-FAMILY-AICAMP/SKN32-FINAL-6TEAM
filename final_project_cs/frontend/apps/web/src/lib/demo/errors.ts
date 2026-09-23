export type GatewayErrorCode =
  | "NOT_FOUND"
  | "CORRUPT_STORAGE"
  | "STORAGE_UNAVAILABLE"
  | "INVALID_INPUT"
  | "VERIFICATION_BLOCKED"
  | "NOT_READY"
  | "DATA_MODE_UNAVAILABLE";

export class GatewayError extends Error {
  constructor(public readonly code: GatewayErrorCode, message: string) {
    super(message);
    this.name = "GatewayError";
  }
}

export function isGatewayError(error: unknown): error is GatewayError {
  return error instanceof GatewayError;
}
