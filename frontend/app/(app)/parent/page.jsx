"use client";
import Gate from "../../../src/Gate";
import ParentDashboard from "../../../src/views/parent/ParentDashboard";

export default function Page() {
  return (
    <Gate page="parent" requiredRole="parent">
      <ParentDashboard />
    </Gate>
  );
}