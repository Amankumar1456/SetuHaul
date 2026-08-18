/**
 * Typing Animation Component
 * Shows animated dots while agent is thinking
 */

export function TypingAnimation() {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-sm text-muted-foreground">Agent is thinking</span>
      <div className="flex gap-1">
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: "0ms" }} />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: "150ms" }} />
        <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: "300ms" }} />
      </div>
    </div>
  );
}
