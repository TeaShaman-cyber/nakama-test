(* GitHub Pages Blog Contract — formal companion projection, 2026-07-22 *)

states = {
  Draft, Ready, GitCommitted, GitReadbackVerified, Published,
  SiteBuildPending, SiteVerified, SiteDegraded, ReturnToCycle,
  Blocked, Unknown
};

terminals = {ReturnToCycle, Blocked, Unknown};

transitions = {
  Draft -> Ready,
  Ready -> GitCommitted,
  GitCommitted -> GitReadbackVerified,
  GitReadbackVerified -> Published,
  Published -> SiteBuildPending,
  SiteBuildPending -> SiteVerified,
  SiteBuildPending -> SiteDegraded,
  SiteVerified -> ReturnToCycle,
  SiteDegraded -> ReturnToCycle,
  Draft -> Blocked,
  Ready -> Blocked,
  GitCommitted -> Blocked,
  GitCommitted -> Unknown,
  GitReadbackVerified -> Unknown
};

g = Graph[transitions, DirectedEdges -> True];

reachableTerminalQ[s_] := AnyTrue[terminals, GraphDistance[g, s, #] < Infinity &];
allStatesTerminate = And @@ (reachableTerminalQ /@ states);

constraints = And[
  Implies[PublishedQ, GitReadbackQ],
  Implies[SiteVerifiedQ, PublishedQ],
  Implies[SiteDegradedQ, PublishedQ],
  Not[SiteVerifiedQ && SiteDegradedQ],
  Implies[SiteVerifiedQ || SiteDegradedQ, CanonicalPreservedQ],
  Not[PagesWritesCanonicalQ]
];

badPublishedWithoutReadback = SatisfiableQ[constraints && PublishedQ && !GitReadbackQ];
badVerifiedWithoutPublication = SatisfiableQ[constraints && SiteVerifiedQ && !PublishedQ];
badDegradedWithoutPublication = SatisfiableQ[constraints && SiteDegradedQ && !PublishedQ];
badCanonicalWrite = SatisfiableQ[constraints && PagesWritesCanonicalQ];
validDegradedState = SatisfiableQ[
  constraints && PublishedQ && GitReadbackQ && SiteDegradedQ &&
  CanonicalPreservedQ && !SiteVerifiedQ
];

AllPassed = And[
  allStatesTerminate,
  !badPublishedWithoutReadback,
  !badVerifiedWithoutPublication,
  !badDegradedWithoutPublication,
  !badCanonicalWrite,
  validDegradedState
];

<|
  "AllStatesTerminate" -> allStatesTerminate,
  "NoPublishedWithoutReadback" -> !badPublishedWithoutReadback,
  "NoSiteVerifiedWithoutPublication" -> !badVerifiedWithoutPublication,
  "NoSiteDegradedWithoutPublication" -> !badDegradedWithoutPublication,
  "NoPagesWriteToCanonical" -> !badCanonicalWrite,
  "DegradedPresentationWithVerifiedPublicationIsRepresentable" -> validDegradedState,
  "AllPassed" -> AllPassed
|>
