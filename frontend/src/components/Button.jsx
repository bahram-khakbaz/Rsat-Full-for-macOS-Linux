import { useSession } from '../session.jsx';

/**
 * Standard action button. `perm` names the API permission the action needs;
 * without it the button is disabled (the API enforces it regardless).
 */
export function Button({
  children,
  kind = '',
  icon: Icon,
  onClick,
  type = 'button',
  disabled = false,
  perm,
  title,
}) {
  const { can } = useSession();
  const denied = Boolean(perm) && !can(perm);
  return (
    <button
      type={type}
      disabled={disabled || denied}
      title={denied ? 'Your role does not include ' + perm : title}
      className={'btn ' + kind}
      onClick={onClick}
    >
      {Icon && <Icon size={14} />}
      <span>{children}</span>
    </button>
  );
}
