import { MurmurMark } from "./MurmurMark";

/** The horizontal lockup: mark followed by the "murmur" wordmark.
 *
 *  The wordmark is set in the app's own sans (IBM Plex Sans) rather than traced
 *  as paths. The supplied logo uses a geometric grotesque very close to Plex's
 *  proportions, and live text stays crisp at any size, scales with the user's
 *  font settings and remains selectable and searchable. Lowercase and tight
 *  tracking match the original.
 */
export function MurmurLogo({
  markSize = 20,
  className = "",
  showWordmark = true,
}: {
  markSize?: number;
  className?: string;
  showWordmark?: boolean;
}) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      {/* The mark carries an accessible name only when it stands alone. Beside
          the wordmark it is decorative -- titling both makes a screen reader
          announce the brand twice ("Murmur murmur"). */}
      <MurmurMark size={markSize} title={showWordmark ? undefined : "Murmur"} />
      {showWordmark && (
        <span
          className="font-semibold tracking-[-0.02em] leading-none text-foreground"
          style={{ fontSize: markSize * 0.82 }}
        >
          murmur
        </span>
      )}
    </span>
  );
}
