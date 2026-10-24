import { Hero } from "@/components/landing/hero";
import { FeatureSection } from "@/components/landing/feature-section";
import { CirclePreview, PathPreview, TalentPreview, TryShiftPreview } from "@/components/landing/previews";

export default function Home() {
  return (
    <div className="flex flex-col">
      <Hero />

      <div className="page-container border-t border-line">
        <FeatureSection
          id="try"
          step="01 · Workday"
          title="Try a real shift."
          body={
            <>
              <p>Pick one of eight Valley careers and work a simulated day: two trucks and one working dock door, a patient who refuses to walk, a weld the inspector rejects.</p>
              <p>Every choice moves your shift and your coworkers react. Try the first moment right here.</p>
            </>
          }
          cta={{ href: "/sim", label: "Start a workday", employerHref: "/employers", employerLabel: "Open the employer desk" }}
        >
          <TryShiftPreview />
        </FeatureSection>

        <FeatureSection
          id="path"
          step="02 · Path"
          title="See a path that fits your week."
          body={
            <>
              <p>Tell Foothold your hours, budget and commute. You get routes of real programs that respect all of them, or a plain answer that nothing fits yet and why.</p>
              <p>Move the slider to give Maya more or fewer hours and watch her options change.</p>
            </>
          }
          cta={{ href: "/path", label: "Plan my path", employerHref: "/employers", employerLabel: "Open the employer desk" }}
          flip
        >
          <PathPreview />
        </FeatureSection>

        <FeatureSection
          id="found"
          step="03 · Skills"
          title="Get found for what you can do."
          body={
            <>
              <p>What you showed in a workday becomes a skill card. Employers rank cards without your name, school or photo.</p>
              <p>When one wants to know who you are, the request lands in your inbox. You decide.</p>
            </>
          }
          cta={{ href: "/inbox", label: "Open my inbox", employerHref: "/employers", employerLabel: "Find talent" }}
        >
          <TalentPreview />
        </FeatureSection>

        <FeatureSection
          id="circle"
          step="04 · Circles"
          title="You're not doing this alone."
          body={
            <>
              <p>Join a small circle of people climbing the same way in your city. Practice hard conversations with a coach before you have them for real.</p>
            </>
          }
          cta={{ href: "/circle", label: "Open my circle", employerHref: "/employers", employerLabel: "Open the employer desk" }}
          flip
        >
          <CirclePreview />
        </FeatureSection>
      </div>
    </div>
  );
}
