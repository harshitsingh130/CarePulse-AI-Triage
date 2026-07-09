/**
 * Emergency banner shown when EMERGENCY urgency is detected during chat.
 */

interface EmergencyBannerProps {
  visible: boolean;
  onConnect: () => void;
  onDismiss: () => void;
}

export function EmergencyBanner({ visible, onConnect, onDismiss }: EmergencyBannerProps) {
  if (!visible) return null;

  return (
    <div className="emergency-banner" role="alert" aria-live="assertive">
      <div className="emergency-banner__content">
        <strong>Based on your symptoms, we&apos;re alerting medical staff immediately.</strong>
        <p>Would you like to speak with someone right now?</p>
      </div>
      <div className="emergency-banner__actions">
        <button
          className="btn btn--emergency"
          onClick={onConnect}
          aria-label="Connect to medical staff now"
        >
          Connect Now
        </button>
        <button
          className="btn btn--secondary"
          onClick={onDismiss}
          aria-label="Dismiss emergency connection offer"
        >
          Not right now
        </button>
      </div>
    </div>
  );
}
