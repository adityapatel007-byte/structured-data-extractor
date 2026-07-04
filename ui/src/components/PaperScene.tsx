/**
 * PaperScene — the hero's 3D moment.
 *
 * A single sheet of paper floating in soft light, slowly drifting. The paper
 * is not a plain plane — it has faint ruled lines and a stamp mark drawn onto
 * a canvas texture, so at rest it reads as "a document" rather than "a card."
 *
 * Interaction:
 *   - Mouse position parallaxes the paper's rotation (gentle, ~8°).
 *   - When `state === "extracting"`, the sheet dips forward and a soft glow
 *     appears — signals "processing" without a spinner.
 *   - When `state === "extracted"`, the sheet tilts up and the corner folds
 *     over, revealing an ink-green underside — signals "done."
 *
 * Rendering strategy:
 *   - Zero external models. Everything is procedural — a plane + a small
 *     `ExtrudeGeometry` for the folded corner, textured with a Canvas the
 *     component draws once on mount. This keeps bundle size tiny.
 */
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment } from "@react-three/drei";
import { useEffect, useMemo, useRef } from "react";
import type { Group, Mesh } from "three";
import * as THREE from "three";

export type PaperState = "idle" | "extracting" | "extracted";

interface Props {
  state: PaperState;
}

export function PaperScene({ state }: Props) {
  return (
    <div className="relative h-full w-full" data-cursor="focus">
      <Canvas
        camera={{ position: [0, 0.4, 6], fov: 35 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true }}
      >
        <color attach="background" args={[0, 0, 0]} />
        {/* alpha:true + skipping color attach makes the canvas transparent */}
        <ambientLight intensity={0.35} />
        <directionalLight position={[3, 4, 5]} intensity={1.05} castShadow />
        <directionalLight position={[-4, -2, -2]} intensity={0.15} color="#e6c48b" />
        <Environment preset="apartment" background={false} />
        <Sheet state={state} />
      </Canvas>
      {/* Warm vignette layered on top so the sheet reads against soft light */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(closest-side at 60% 40%, transparent 40%, var(--bg) 92%)",
        }}
      />
    </div>
  );
}

/* ------------------------------------------------------------------------ */

function Sheet({ state }: { state: PaperState }) {
  const group = useRef<Group>(null!);
  // Mouse position lives in a ref, not state, so pointer movement doesn't
  // force React re-renders at ~60Hz. `useFrame` reads it directly on the next
  // GPU tick, so parallax stays live without touching the render loop.
  const mouse = useRef({ x: 0, y: 0 });

  // Track the mouse across the whole window — the parallax reads better when
  // it's tied to page position, not just the canvas.
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      mouse.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.current.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  const texture = useMemo(() => paperTexture(), []);

  useFrame((clock, delta) => {
    if (!group.current) return;
    const t = clock.clock.elapsedTime;

    // Base slow drift (idle motion).
    const driftY = Math.sin(t * 0.5) * 0.08;
    const driftRotX = Math.sin(t * 0.4) * 0.05;
    const driftRotZ = Math.cos(t * 0.3) * 0.03;

    // Parallax offset from mouse (ref-based — no React re-renders).
    const paraX = mouse.current.x * 0.14;
    const paraY = mouse.current.y * 0.08;

    // Targets vary by state.
    const targetRotX = state === "extracted" ? -0.35 : driftRotX + paraY * 0.8;
    const targetRotY = state === "extracted" ? -0.15 : paraX * 0.9;
    const targetRotZ = state === "extracting" ? 0.02 : driftRotZ;
    const targetY = state === "extracting" ? -0.15 : driftY;
    const targetScale = state === "extracting" ? 0.97 : 1;

    // Ease each channel toward target.
    const k = 1 - Math.pow(0.001, delta);
    group.current.rotation.x += (targetRotX - group.current.rotation.x) * k;
    group.current.rotation.y += (targetRotY - group.current.rotation.y) * k;
    group.current.rotation.z += (targetRotZ - group.current.rotation.z) * k;
    group.current.position.y += (targetY - group.current.position.y) * k;
    const s = group.current.scale.x + (targetScale - group.current.scale.x) * k;
    group.current.scale.set(s, s, s);
  });

  return (
    <group ref={group}>
      {/* Soft cast shadow beneath the sheet — a squashed dark plane. */}
      <mesh position={[0.05, -1.35, -0.1]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.2, 2.2]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.12} />
      </mesh>

      {/* Main sheet — a slightly wider-than-tall rectangle.
          Uses MeshBasicMaterial so the texture (which already contains its
          own baked-in shading + gradient) reads at full brightness. Standard
          PBR shading was dimming the printed text — user flagged this. */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[2.55, 3.4, 0.02]} />
        <meshBasicMaterial
          map={texture}
          side={THREE.DoubleSide}
          toneMapped={false}
        />
      </mesh>

      {/* Folded corner reveal — only visible when extracted. */}
      <FoldedCorner active={state === "extracted"} />

      {/* Glow puck under the sheet during extraction */}
      <Glow active={state === "extracting"} />
    </group>
  );
}

/* -- folded corner --------------------------------------------------------- */

function FoldedCorner({ active }: { active: boolean }) {
  const meshRef = useRef<Mesh>(null!);

  useFrame((_, delta) => {
    if (!meshRef.current) return;
    const target = active ? 1 : 0;
    const k = 1 - Math.pow(0.001, delta);
    const cur = meshRef.current.userData.progress ?? 0;
    const next = cur + (target - cur) * k;
    meshRef.current.userData.progress = next;
    meshRef.current.scale.setScalar(0.001 + next * 1);
    (meshRef.current.material as THREE.MeshStandardMaterial).opacity = next;
  });

  return (
    <mesh
      ref={meshRef}
      position={[1.05, 1.45, 0.02]}
      rotation={[0, 0, -Math.PI / 4]}
    >
      <planeGeometry args={[0.9, 0.9]} />
      <meshStandardMaterial
        color="#7f9c78"
        roughness={0.8}
        transparent
        opacity={0}
      />
    </mesh>
  );
}

/* -- glow puck ------------------------------------------------------------- */

function Glow({ active }: { active: boolean }) {
  const meshRef = useRef<Mesh>(null!);

  useFrame((clock, delta) => {
    if (!meshRef.current) return;
    const target = active ? 1 : 0;
    const k = 1 - Math.pow(0.001, delta);
    const mat = meshRef.current.material as THREE.MeshBasicMaterial;
    const cur = mat.opacity;
    mat.opacity = cur + (target * 0.6 - cur) * k;
    const scale = 1 + Math.sin(clock.clock.elapsedTime * 2) * 0.06 * target;
    meshRef.current.scale.setScalar(scale);
  });

  return (
    <mesh ref={meshRef} position={[0, 0, -0.6]}>
      <circleGeometry args={[1.6, 64]} />
      <meshBasicMaterial color="#e6604f" transparent opacity={0} />
    </mesh>
  );
}

/* -- procedural texture ---------------------------------------------------- */

/**
 * Paints a paper-like canvas: warm cream base, faint ruled lines, a subtle
 * stamp mark, and a "TOTAL" label near the bottom. Just enough visual noise
 * that the sheet reads as a document rather than a blank plane.
 */
function paperTexture(): THREE.CanvasTexture {
  // Draw at 2× so the sheet stays sharp when the camera is close.
  // `ctx.scale` lets us keep all layout coordinates in the original 512×680
  // logical space — every font-size and offset below is unchanged.
  const SCALE = 2;
  const LOGICAL_W = 512;
  const LOGICAL_H = 680;
  const c = document.createElement("canvas");
  c.width = LOGICAL_W * SCALE;
  c.height = LOGICAL_H * SCALE;
  const ctx = c.getContext("2d")!;
  ctx.scale(SCALE, SCALE);
  // From here on, treat the drawing surface as if it were LOGICAL_W × LOGICAL_H.
  // Local aliases keep the layout math readable.
  const cw = LOGICAL_W;
  const ch = LOGICAL_H;

  // Base paper — warm cream with a subtle gradient
  const grad = ctx.createLinearGradient(0, 0, 0, ch);
  grad.addColorStop(0, "#f8f2e2");
  grad.addColorStop(1, "#efe8d0");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, cw, ch);

  // Speckle grain
  for (let i = 0; i < 2200; i++) {
    ctx.fillStyle = `rgba(120,100,60,${Math.random() * 0.04})`;
    ctx.fillRect(
      Math.random() * cw,
      Math.random() * ch,
      Math.random() * 1.6,
      Math.random() * 1.6
    );
  }

  // Header rule
  ctx.strokeStyle = "rgba(16,32,59,0.75)";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(40, 96);
  ctx.lineTo(cw - 40, 96);
  ctx.stroke();

  // Vendor/merchant label
  ctx.fillStyle = "#10203b";
  ctx.font = 'italic 34px "Instrument Serif", serif';
  ctx.fillText("Invoice", 40, 76);

  // Ruled body lines (light)
  ctx.strokeStyle = "rgba(16,32,59,0.09)";
  ctx.lineWidth = 1;
  for (let y = 130; y < ch - 120; y += 26) {
    ctx.beginPath();
    ctx.moveTo(40, y);
    ctx.lineTo(cw - 40, y);
    ctx.stroke();
  }

  // Fake line items
  ctx.fillStyle = "rgba(16,32,59,0.55)";
  ctx.font = '13px "JetBrains Mono", monospace';
  const rows: [string, string][] = [
    ["Software license", "$1,240.00"],
    ["Support (annual)", "  $360.00"],
    ["Onboarding", "  $200.00"],
  ];
  rows.forEach(([desc, amt], i) => {
    ctx.fillText(desc, 40, 156 + i * 26);
    ctx.fillText(amt, cw - 130, 156 + i * 26);
  });

  // Total
  ctx.strokeStyle = "rgba(16,32,59,0.55)";
  ctx.beginPath();
  ctx.moveTo(40, 260);
  ctx.lineTo(cw - 40, 260);
  ctx.stroke();

  ctx.fillStyle = "#10203b";
  ctx.font = 'italic 22px "Instrument Serif", serif';
  ctx.fillText("Total", 40, 292);
  ctx.font = 'italic 22px "Instrument Serif", serif';
  ctx.fillText("$1,800.00", cw - 140, 292);

  // Bottom stamp — a red circle with "PAID" (ish)
  const cx = cw - 110;
  const cy = ch - 110;
  ctx.save();
  ctx.translate(cx, cy);
  ctx.rotate(-0.18);
  ctx.strokeStyle = "rgba(197,58,44,0.75)";
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.arc(0, 0, 52, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(0, 0, 46, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = "rgba(197,58,44,0.85)";
  ctx.font = 'bold 20px "Geist", sans-serif';
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText("PAID", 0, 0);
  ctx.restore();

  const tex = new THREE.CanvasTexture(c);
  // Sharpness knobs — user flagged text as bitty on the hero.
  // • LinearFilter (no mipmap blur) keeps small type crisp at close camera range.
  // • anisotropy 16 keeps text readable at glancing angles as the sheet tilts.
  // • generateMipmaps off — we don't need distance LODs for a hero prop.
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  tex.anisotropy = 16;
  tex.generateMipmaps = false;
  tex.needsUpdate = true;
  return tex;
}
