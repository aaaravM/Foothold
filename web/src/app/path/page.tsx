import type { Metadata } from "next";
import { PathPage } from "@/components/path/path-page";

export const metadata: Metadata = { title: "Path" };

export default function Page() {
  return <PathPage />;
}
