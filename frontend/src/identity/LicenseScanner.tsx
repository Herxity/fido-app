import type { IScannerControls } from "@zxing/browser";
import { Camera, ScanLine, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { parseLicenseBarcode, type ParsedLicense } from "./licenseScan";

export function LicenseScanner({ onParsed }: { onParsed: (value: ParsedLicense) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const controls = useRef<IScannerControls | null>(null);
  const [raw, setRaw] = useState("");
  const [cameraOpen, setCameraOpen] = useState(false);
  const [message, setMessage] = useState("");

  const apply = (value: string) => {
    try {
      onParsed(parseLicenseBarcode(value));
      setRaw("");
      setMessage("License fields captured. Compare them with the printed card before submitting.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "The barcode could not be parsed.");
    }
  };

  const closeCamera = () => {
    controls.current?.stop();
    controls.current = null;
    setCameraOpen(false);
  };

  useEffect(() => () => controls.current?.stop(), []);

  const scanCamera = async () => {
    setCameraOpen(true);
    setMessage("Point the camera at the PDF417 barcode on the back of the card.");
    try {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const { BrowserPDF417Reader } = await import("@zxing/browser");
      controls.current = await new BrowserPDF417Reader().decodeFromVideoDevice(undefined, video.current || undefined, (result) => {
        if (!result) return;
        apply(result.getText());
        closeCamera();
      });
    } catch (error) {
      setMessage(error instanceof Error && error.name === "NotAllowedError" ? "Camera permission was denied. Use a scanner or manual entry." : "No barcode was captured. Hold the card steady and try again.");
      closeCamera();
    }
  };

  return <section className="scan-ledger" aria-labelledby="scan-heading">
    <div><p className="eyebrow">Assisted entry</p><h2 id="scan-heading">Scan the back of the ID</h2><p>Camera decoding happens in this browser. Barcode images and raw scan strings are not uploaded or retained.</p></div>
    <div className="scan-actions"><button type="button" className="button secondary" onClick={() => void scanCamera()}><Camera size={17} /> Use camera</button></div>
    {cameraOpen && <div className="camera-frame"><video ref={video} muted playsInline aria-label="License barcode camera preview" /><button type="button" className="icon-button camera-close" onClick={closeCamera} aria-label="Close camera"><X /></button></div>}
    <label htmlFor="scanner-payload">USB or Bluetooth scanner input</label>
    <div className="scan-input"><textarea id="scanner-payload" rows={3} value={raw} onChange={(event) => setRaw(event.target.value)} placeholder="Focus here, then scan the PDF417 barcode" maxLength={20000} /><button type="button" className="button secondary" disabled={!raw.trim()} onClick={() => apply(raw)}><ScanLine size={17} /> Parse scan</button></div>
    {message && <p className="status-note" role="status">{message}</p>}
  </section>;
}
