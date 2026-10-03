import { memo } from "react";

/* A pure-CSS 3D robot used as Novi's avatar in chat. No assets, no deps — the
   depth comes from layered gradients, inset highlights and a 3D transform on
   the body. `state` drives the idle animation: "idle" breathes, "typing" leans
   in and bobs faster, matching the "Typing…" status in the chat header. */
function NoviRobot({ state = "idle", className = "" }) {
  return (
    <span className={`novi-bot${className ? " " + className : ""} is-${state}`} aria-hidden="true">
      <span className="nb-antenna">
        <span className="nb-antenna-ball" />
      </span>
      <span className="nb-head">
        <span className="nb-ear nb-ear-l" />
        <span className="nb-ear nb-ear-r" />
        <span className="nb-visor">
          <span className="nb-eye nb-eye-l" />
          <span className="nb-eye nb-eye-r" />
        </span>
        <span className="nb-mouth" />
      </span>
      <span className="nb-neck" />
      <span className="nb-body">
        <span className="nb-core" />
        <span className="nb-seam" />
      </span>
    </span>
  );
}

export default memo(NoviRobot);