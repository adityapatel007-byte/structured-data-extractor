/**
 * App — page composition. Hero, workbench, chapters, numbers, footer.
 * The 3D paper's state is lifted here so the hero can react to extraction.
 */
import { useCallback, useRef, useState } from "react";

import { CustomCursor } from "./components/CustomCursor";
import { ExtractSection } from "./components/ExtractSection";
import { Footer } from "./components/Footer";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { Numbers } from "./components/Numbers";
import { TopNav } from "./components/TopNav";
import type { PaperState } from "./components/PaperScene";

export default function App() {
  const [paperState, setPaperState] = useState<PaperState>("idle");
  const heroCTA = useRef<() => void>(() => {});

  const bindExtract = useCallback((fn: () => void) => {
    heroCTA.current = fn;
  }, []);

  return (
    <div className="cursor-ink">
      <CustomCursor />
      <TopNav />
      <main>
        <Hero
          paperState={paperState}
          onCTAClick={() => heroCTA.current()}
        />
        <ExtractSection
          onStateChange={setPaperState}
          bindExtract={bindExtract}
        />
        <HowItWorks />
        <Numbers />
      </main>
      <Footer />
    </div>
  );
}
