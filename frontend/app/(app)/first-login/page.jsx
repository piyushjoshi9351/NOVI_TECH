"use client";

import Gate from "../../../src/Gate";
import FirstLogin from "../../../src/views/FirstLogin";

export default function Page() {
  return <Gate requiredRole="student"><FirstLogin /></Gate>;
}
