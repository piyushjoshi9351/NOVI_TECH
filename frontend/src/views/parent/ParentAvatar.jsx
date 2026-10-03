import { useEffect, useState } from "react";
import { apiImage, esc, initials } from "../../api";

export function ParentAvatar({ studentId, name, className = "", size = 44 }) {
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let live = true;
    if (!studentId) { setSrc(null); return undefined; }
    const p = apiImage(`/parent/students/${studentId}/photo`);
    Promise.resolve(p).then((u) => { if (live) setSrc(u || null); });
    return () => { live = false; };
  }, [studentId]);

  const style = { width: size, height: size };
  if (src) {
    return (
      <img
        className={`pd-avatar-img ${className}`}
        style={style}
        src={src}
        alt=""
        onError={() => setSrc(null)}
      />
    );
  }
  return (
    <span className={`pd-avatar-ini ${className}`} style={style} aria-hidden="true">
      {esc(initials(name))}
    </span>
  );
}