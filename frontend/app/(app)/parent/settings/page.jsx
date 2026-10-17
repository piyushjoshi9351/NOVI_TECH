"use client";

import Gate from "../../../../src/Gate";
import ParentSettings from "../../../../src/views/parent/ParentSettings";

export default function Page() {
  return <Gate requiredRole="parent"><ParentSettings /></Gate>;
}
