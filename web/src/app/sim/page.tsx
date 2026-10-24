import type { Metadata } from "next";
import { SimPage } from "@/components/sim/sim-page";

export const metadata: Metadata = { title: "Sim" };

export default function Page() {
  return <SimPage />;
}
