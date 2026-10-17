"use client";

import Gate from "../../../../src/Gate";
import AddChild from "../../../../src/views/parent/AddChild";

export default function Page() {
  return <Gate requiredRole="parent"><AddChild /></Gate>;
}
