/**
 * Message Enhancement Utilities
 * Parses driver assistant messages to extract:
 * - Exception types (shown as badges)
 * - Follow-up questions (highlighted)
 * - Key information (emphasized)
 */

export interface MessagePart {
  type: "text" | "exception" | "question" | "highlight";
  content: string;
}

// Exception type patterns
const EXCEPTION_PATTERNS: Record<string, string> = {
  "MECHANICAL_FAILURE": "Mechanical Issue",
  "DRIVER_SICKNESS": "Driver Health",
  "TRAFFIC_CONGESTION": "Traffic Delay",
  "POLICE_CHECKPOINT": "Police Checkpoint",
  "FACILITY_BLOCKED": "Facility Issue",
  "GENERIC_DELAY": "Delay",
};

/**
 * Extract exception type from message if mentioned
 */
export function extractExceptionType(text: string): string | null {
  for (const [type, _label] of Object.entries(EXCEPTION_PATTERNS)) {
    if (text.includes(type)) {
      return type;
    }
  }
  return null;
}

/**
 * Get human-readable exception label
 */
export function getExceptionLabel(type: string): string {
  return EXCEPTION_PATTERNS[type] || type;
}

/**
 * Extract follow-up questions from message
 * Questions typically end with "?" and are short sentences
 */
export function extractFollowUpQuestions(text: string): string[] {
  // Match sentences ending with "?"
  const questionRegex = /[^.!?]*\?/g;
  const matches = text.match(questionRegex) || [];
  
  return matches
    .map((q) => q.trim())
    .filter((q) => q.length > 10 && q.length < 200); // Filter very short/long
}

/**
 * Highlight key information in messages
 * - Time mentions (e.g., "2 hours", "30 mins")
 * - Facility codes (e.g., "FAC-001", "WH-A")
 * - Status words (e.g., "CONFIRMED", "AVAILABLE")
 */
export function highlightKeyInfo(text: string): string {
  let highlighted = text;

  // Highlight time mentions (e.g., "2 hours", "30 mins")
  highlighted = highlighted.replace(
    /(\d+\s*(?:hour|hr|minute|min|second|sec)[s]?)/gi,
    '<span class="font-semibold text-accent">$1</span>'
  );

  // Highlight facility codes (e.g., FAC-001, WH-A)
  highlighted = highlighted.replace(
    /(FAC-\d{3}|WH-[A-F])/gi,
    '<span class="font-semibold text-primary">$1</span>'
  );

  // Highlight shipment IDs (e.g., SHP-12345)
  highlighted = highlighted.replace(
    /(SHP-[A-Z0-9]{6})/gi,
    '<span class="font-semibold text-primary">$1</span>'
  );

  // Highlight status keywords
  highlighted = highlighted.replace(
    /\b(CONFIRMED|AVAILABLE|BOOKED|PENDING|CANCELLED|DELAYED)\b/gi,
    '<span class="font-semibold text-success">$1</span>'
  );

  // Highlight warnings
  highlighted = highlighted.replace(
    /\b(WARNING|ALERT|ERROR|ISSUE|PROBLEM|CANNOT|UNABLE)\b/gi,
    '<span class="font-semibold text-destructive">$1</span>'
  );

  return highlighted;
}

/**
 * Format message for display
 * Returns HTML-safe string with highlighting
 */
export function formatMessage(text: string): string {
  // First apply highlighting
  let formatted = highlightKeyInfo(text);

  // Escape any remaining HTML
  formatted = formatted
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  // Then re-apply the HTML highlighting (since we replaced it)
  formatted = formatted.replace(/&lt;span/g, "<span").replace(/&lt;\/span&gt;/g, "</span>");

  return formatted;
}

/**
 * Parse location test response
 */
export function parseLocationResponse(data: unknown): {
  latitude: number;
  longitude: number;
  name: string;
  description: string;
} | null {
  if (
    typeof data === "object" &&
    data !== null &&
    "latitude" in data &&
    "longitude" in data
  ) {
    return {
      latitude: (data as any).latitude,
      longitude: (data as any).longitude,
      name: (data as any).name || "Test Location",
      description: (data as any).description || "",
    };
  }
  return null;
}

/**
 * Generate a message to send when location is shared
 */
export function generateLocationMessage(location: {
  latitude: number;
  longitude: number;
  name: string;
}): string {
  return `📍 Sharing my location: ${location.name} (${location.latitude.toFixed(4)}, ${location.longitude.toFixed(4)})`;
}
