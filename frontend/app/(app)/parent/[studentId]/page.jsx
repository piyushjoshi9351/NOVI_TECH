"use client";
import { useParams } from "next/navigation";
import Gate from "../../../../src/Gate";
import ParentStudent from "../../../../src/views/parent/ParentStudent";

export default function Page() {
  const params = useParams();
  return (
    <Gate page="parent" requiredRole="parent">
      <ParentStudent studentId={params?.studentId} />
    </Gate>
  );
}