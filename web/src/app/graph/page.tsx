"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** The skills graph explorer was retired; its GNN picks now live on /path ("Picked for you"). */
export default function GraphPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/path");
  }, [router]);
  return null;
}
