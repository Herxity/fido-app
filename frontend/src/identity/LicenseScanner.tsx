import type { BrowserPDF417Reader, IScannerControls } from "@zxing/browser";
import { Camera, ScanLine, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { parseLicenseBarcode, type ParsedLicense } from "./licenseScan";

export function LicenseScanner({ onParsed }: { onParsed: (value: ParsedLicense) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const controls = useRef<IScannerControls | null>(null);
  const reader = useRef<BrowserPDF417Reader | null>(null);
  const capturing = useRef(false);
  const guidanceTimer = useRef<number | null>(null);
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
    reader.current = null;
    capturing.current = false;
    if (guidanceTimer.current !== null) window.clearTimeout(guidanceTimer.current);
    guidanceTimer.current = null;
    setCameraOpen(false);
  };

  useEffect(() => () => controls.current?.stop(), []);

  const captureCurrentFrame = (detectedText?: string) => {
    if (capturing.current || !video.current || !reader.current) return;
    const source = video.current;
    if (!source.videoWidth || !source.videoHeight) {
      setMessage("The camera is still starting. Wait a moment, then take the photo.");
      return;
    }
    capturing.current = true;
    setMessage(detectedText ? "Barcode detected—capturing this frame…" : "Capturing and reading this frame…");
    const canvas = document.createElement("canvas");
    canvas.width = source.videoWidth;
    canvas.height = source.videoHeight;
    canvas.getContext("2d", { alpha: false })?.drawImage(source, 0, 0, canvas.width, canvas.height);
    try {
      const text = detectedText || reader.current.decodeFromCanvas(canvas).getText();
      apply(text);
      closeCamera();
    } catch {
      capturing.current = false;
      setMessage("That frame did not resolve the barcode. Move closer, avoid glare, keep the barcode level, and take another photo.");
    } finally {
      canvas.width = 0;
      canvas.height = 0;
    }
  };

  const scanCamera = async () => {
    setCameraOpen(true);
    setMessage("Point the camera at the PDF417 barcode on the back of the card.");
    try {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      const [{ BrowserPDF417Reader }, { DecodeHintType }] = await Promise.all([import("@zxing/browser"), import("@zxing/library")]);
      const hints = new Map();
      hints.set(DecodeHintType.TRY_HARDER, true);
      reader.current = new BrowserPDF417Reader(hints, { delayBetweenScanAttempts: 80 });
      controls.current = await reader.current.decodeFromConstraints({ audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 }, aspectRatio: { ideal: 16 / 9 } } }, video.current || undefined, (result) => {
        if (!result) return;
        captureCurrentFrame(result.getText());
      });
      guidanceTimer.current = window.setTimeout(() => setMessage("Still looking… fill the guide with the wide barcode and hold steady, or press Take photo to decode the current frame."), 7000);
    } catch (error) {
      setMessage(error instanceof Error && error.name === "NotAllowedError" ? "Camera permission was denied. Use a scanner or manual entry." : "No barcode was captured. Hold the card steady and try again.");
      closeCamera();
    }
  };

  return <section className="scan-ledger" aria-labelledby="scan-heading">
    <div><p className="eyebrow">Assisted entry</p><h2 id="scan-heading">Scan the back of the ID</h2><p>Camera decoding happens in this browser. Barcode images and raw scan strings are not uploaded or retained.</p></div>
    <div className="scan-actions"><button type="button" className="button secondary" disabled={cameraOpen} onClick={() => void scanCamera()}><Camera size={17} /> Open camera</button></div>
    {cameraOpen && <div className="camera-frame"><video ref={video} muted playsInline aria-label="License barcode camera preview" /><div className="barcode-guide" aria-hidden="true"><span /></div><div className="camera-controls"><span>Auto-captures when the barcode is detected</span><button type="button" className="button primary" onClick={() => captureCurrentFrame()}><Camera size={17} /> Take photo</button></div><button type="button" className="icon-button camera-close" onClick={closeCamera} aria-label="Close camera"><X /></button></div>}
    <label htmlFor="scanner-payload">USB or Bluetooth scanner input</label>
    <div className="scan-input"><textarea id="scanner-payload" rows={3} value={raw} onChange={(event) => setRaw(event.target.value)} placeholder="Focus here, then scan the PDF417 barcode" maxLength={20000} /><button type="button" className="button secondary" disabled={!raw.trim()} onClick={() => apply(raw)}><ScanLine size={17} /> Parse scan</button></div>
    {message && <p className="status-note" role="status">{message}</p>}
  </section>;
}
