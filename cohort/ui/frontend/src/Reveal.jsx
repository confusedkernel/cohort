import { useDisclosure } from './motion'

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
  const { mounted, expanded, settled } = useDisclosure(open, 220)
  if (!mounted) return null
  return (
    <div className="reveal" data-open={expanded || undefined} data-settled={settled || undefined}>
      <div className="reveal-in">{children}</div>
    </div>
  )
}
