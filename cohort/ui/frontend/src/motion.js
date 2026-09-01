import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

// Shared motion machinery: the two things the surfaces below need and React
// does not give them.
//
//   1. `usePresence` — a floating panel that animates *out*. React unmounts a
//      conditional child the instant the condition flips, which is why every
//      popover here had an entrance and no exit: the inspector and the two
//      top-bar popovers slid in and then vanished on a frame. The hook holds
//      the element mounted for the length of its exit animation and marks it
//      `closing` while that plays.
//
//   2. `useSlidingIndicator` — the moving thumb behind a segmented control.
//      The active segment is measured in the DOM, so one raised surface
//      travels between segments of unequal width instead of a background
//      switching off in one place and on in another.
//
// Both defer to `prefers-reduced-motion`. styles.css squashes every duration
// to nothing for that reader, so the JS must match: a panel held mounted and
// invisible for 180ms after it closed would swallow the next click, and a
// thumb is a placement rather than a journey.

export function prefersReducedMotion() {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  } catch {
    // A browser without matchMedia gets motion; it is decoration either way.
    return false
  }
}

// Keeps `open === false` on screen until its exit animation has played.
//
// `exitMs` must match the CSS: too short and the panel is cut off mid-fade,
// too long and a closed panel keeps its space in the accessibility tree.
export function usePresence(open, exitMs = 180) {
  const [mounted, setMounted] = useState(open)

  useEffect(() => {
    if (open) { setMounted(true); return undefined }
    if (prefersReducedMotion()) { setMounted(false); return undefined }
    const t = setTimeout(() => setMounted(false), exitMs)
    return () => clearTimeout(t)
  }, [open, exitMs])

  // `mounted || open` covers the frame between the prop flipping to true and
  // the effect running — without it an opening panel is a frame late.
  return { mounted: mounted || open, closing: mounted && !open }
}

// Drives an in-flow disclosure — a region that grows the layout open rather
// than appearing at full size in one frame. See `.reveal` in styles.css and
// Reveal.jsx; the three phases are what a CSS-only version cannot express:
//
//   mounted   the children are in the DOM. Ahead of `expanded` on the way in,
//             behind it on the way out, so both directions have something to
//             animate.
//   expanded  the class that drives the height. Deliberately one frame late,
//             because a transition needs a starting frame at zero.
//   settled   the growth has finished, and the clip that made it possible can
//             be dropped — an `overflow: hidden` box cuts the focus ring off
//             the control inside it.
export function useDisclosure(open, ms = 220) {
  const { mounted } = usePresence(open, ms)
  const [expanded, setExpanded] = useState(false)
  const [settled, setSettled] = useState(false)

  useEffect(() => {
    if (!open) { setExpanded(false); setSettled(false); return undefined }
    if (prefersReducedMotion()) { setExpanded(true); setSettled(true); return undefined }
    const frame = requestAnimationFrame(() => setExpanded(true))
    const done = setTimeout(() => setSettled(true), ms + 40)
    return () => { cancelAnimationFrame(frame); clearTimeout(done) }
  }, [open, ms])

  return { mounted, expanded, settled }
}

// Measures the active segment of a segmented control so a single thumb can
// slide to it. The caller puts `trackRef` on the track, spreads `thumbProps`
// onto a `<span>` inside it, and marks each segment `data-seg-on={active}`.
//
// `rendered` says whether the track is in the DOM at all — the theme picker
// lives inside a popover and the tab bar only exists once the graph has
// loaded. A ref attaching is not a render the hook can see, so without it the
// first measurement would wait for a selection that has already been made.
export function useSlidingIndicator(activeKey, segmentCount, rendered = true) {
  const trackRef = useRef(null)
  const [box, setBox] = useState(null)
  const [animate, setAnimate] = useState(false)

  const measure = useCallback(() => {
    const on = trackRef.current?.querySelector('[data-seg-on="true"]')
    if (!on) return
    // Offsets, not bounding rects: the track is the offset parent, so these
    // are already thumb coordinates and survive a page zoom without the
    // sub-pixel drift `getBoundingClientRect` introduces.
    setBox((prev) => (
      prev && prev.left === on.offsetLeft && prev.width === on.offsetWidth
        ? prev
        : { left: on.offsetLeft, width: on.offsetWidth }
    ))
  }, [])

  // Layout effect, so the measurement lands in the same frame as the class
  // change and the thumb is never painted at the outgoing segment.
  useLayoutEffect(measure, [measure, activeKey, segmentCount, rendered])

  // Geometry moves under us for reasons unrelated to the selection: the tab
  // bar goes full width below 760px, coarse pointers raise `--control-h`, and
  // a segment can gain or lose a label.
  useEffect(() => {
    const track = trackRef.current
    if (!track || typeof ResizeObserver === 'undefined') return undefined
    const ro = new ResizeObserver(measure)
    ro.observe(track)
    // The segments only — observing the thumb would feed its own width back in.
    track.querySelectorAll('[data-seg-on]').forEach((el) => ro.observe(el))
    return () => ro.disconnect()
  }, [measure, segmentCount, rendered])

  // The first measurement can be taken against a fallback font, which is a
  // few pixels off in every label.
  useEffect(() => {
    let live = true
    document.fonts?.ready?.then(() => { if (live) measure() }).catch(() => {})
    return () => { live = false }
  }, [measure])

  // The first position is a placement, not a move. Transitions come on one
  // frame later so the thumb does not fly in from the track's left edge.
  useEffect(() => {
    if (!box || animate || prefersReducedMotion()) return undefined
    const r = requestAnimationFrame(() => setAnimate(true))
    return () => cancelAnimationFrame(r)
  }, [box, animate])

  return {
    trackRef,
    thumbProps: {
      className: 'seg-thumb',
      'aria-hidden': true,
      'data-animate': animate || undefined,
      style: box
        ? { width: `${box.width}px`, transform: `translateX(${box.left}px)`, opacity: 1 }
        : undefined,
    },
  }
}
