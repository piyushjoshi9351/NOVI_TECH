"use client";
import Gate from "../../../../src/Gate";
import ParentStudent from "../../../../src/views/parent/ParentStudent";

export default function Page() {
  return (
    <Gate page="parent" requiredRole="parent">
      <ParentStudent />
    </Gate>
  );
}