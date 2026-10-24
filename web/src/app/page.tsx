import { Hero } from "@/components/landing/hero";
import { StageScroll } from "@/components/landing/stage-scroll";
import { ClosingCta } from "@/components/landing/closing-cta";

export default function Home() {
  return (
    <div className="flex flex-col">
      <Hero />
      <StageScroll />
      <ClosingCta />
    </div>
  );
}
