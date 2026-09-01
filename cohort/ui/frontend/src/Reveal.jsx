import { useEffect, useRef, useState } from 'react'
import { prefersReducedMotion, useDisclosure } from './motion'

const MS = 220

// An in-flow disclosure: a region that grows and collapses instead of
// appearing and vanishing.
//
// Every use of it is inside the floating inspector or a list row — the retract
// form under an edge, an author's contribution history, the refusal a write
// came back with, a corpus record. That is where a jump hurts most: the
// inspector is a fixed-height box that scrolls, so a form arriving at full
// size shoves everything below it in a single frame and takes the line the
// reader was looking at with it.
//
// Two elements, because a height transition needs both: the outer grid
// animates `0fr -> 1fr`, which is the only way CSS can transition *to* a
// content height, and the inner box supplies the clip that makes the partial
// height show partial content. See `.reveal` in styles.css.
export default function Reveal({ open, children }) {
  const { mounted, expanded } = useDisclosure(open, MS)
  // The clip has to come off once the growth is done — `overflow: hidden` cuts
  // the focus ring off the textarea and buttons inside — but only *once it is
  // done*, or a nested disclosure gets un-clipped while it is still opening.
  // Driven by the event rather than a timer because the growth does not start
  // on a predictable frame; the timeout is only a backstop for the case where
  // no transition runs at all and no event is coming.
  const [settled, setSettled] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!expanded) { setSettled(false); return undefined }
    if (prefersReducedMotion()) { setSettled(true); return undefined }
    const backstop = setTimeout(() => setSettled(true), MS * 3)
    return () => clearTimeout(backstop)
  }, [expanded])

  if (!mounted) return null
  return (
    <div
      ref={ref}
      className="reveal"
      data-open={expanded || undefined}
      data-settled={settled || undefined}
      onTransitionEnd={(e) => {
        if (e.target === ref.current && e.propertyName === 'grid-template-rows') {
          setSettled(expanded)
        }
      }}
    >
      <div className="reveal-in">{children}</div>
    </div>
  )
}
