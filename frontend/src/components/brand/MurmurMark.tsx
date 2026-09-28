/** The Murmur mark: a soundwave that reads as a lowercase "m".
 *
 *  Traced as vector rather than cropped from the supplied PDF, because that file
 *  embeds one 2160x1560 JPEG of the whole brand sheet with the cream and black
 *  backgrounds baked in and no alpha channel. Cropping it would paint a light
 *  rectangle behind the mark everywhere it sits on a dark surface, and a bitmap
 *  would soften at the 18-20px the nav actually renders it at.
 *
 *  The glyph is one continuous stroke with round caps and joins: it starts low
 *  on the left, rises through two humps (the second taller, as in the original)
 *  and hooks down to the right. Drawn as a stroke, not a filled outline, so its
 *  weight stays optically even at every size.
 */

interface Props {
  /** Pixel size of the square. */
  size?: number;
  /** Draw the enclosing disc. False gives the bare glyph for tight spaces. */
  disc?: boolean;
  className?: string;
  title?: string;
}

export function MurmurMark({ size = 20, disc = true, className = "", title }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      {disc && <circle cx="32" cy="32" r="32" fill="currentColor" />}
      <path
        d="M17 39.5 C 17.2 29.4, 19.3 23.7, 24.4 23.7 C 29.6 23.7, 31.2 32.4, 34.4 32.4 C 37.9 32.4, 39.1 16.5, 45.3 16.5 C 50.4 16.5, 50.9 28.4, 54.9 28.4"
        // The glyph is knocked out of the disc, so it takes the surface color
        // behind the mark rather than a fixed white -- the same component then
        // works on the dark nav and on a light surface without a variant.
        stroke={disc ? "var(--murmur-knockout, #F5F3EF)" : "currentColor"}
        strokeWidth="6.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
