// Line icons, drawn on a 24 grid with a single stroke weight so they sit together well.

type IconProps = { size?: number; className?: string };

function Svg({ size = 20, className, children }: IconProps & { children: React.ReactNode }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" focusable="false">{children}</svg>;
}

export const ArrowRight = (props: IconProps) => <Svg {...props}>
  <path d="M4 12h15M13 6l6 6-6 6" />
</Svg>;

export const ArrowLeft = (props: IconProps) => <Svg {...props}>
  <path d="M20 12H5M11 18l-6-6 6-6" />
</Svg>;

export const Check = (props: IconProps) => <Svg {...props}>
  <path d="M5 12.5l4.5 4.5L19 7" />
</Svg>;

export const Download = (props: IconProps) => <Svg {...props}>
  <path d="M12 4v11M7.5 10.5L12 15l4.5-4.5M5 19h14" />
</Svg>;

export const Sparkle = (props: IconProps) => <Svg {...props}>
  <path d="M12 4l1.7 4.6L18 10.2l-4.3 1.6L12 16.4l-1.7-4.6L6 10.2l4.3-1.6zM18.5 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z" />
</Svg>;

export const Document = (props: IconProps) => <Svg {...props}>
  <path d="M6.5 3.5h7l4.5 4.5v12a1 1 0 0 1-1 1h-10.5a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1z" />
  <path d="M13.5 3.5V8H18M9 13h6M9 16.5h4" />
</Svg>;

export const Sun = (props: IconProps) => <Svg {...props}>
  <circle cx="12" cy="12" r="4" />
  <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" />
</Svg>;

export const Moon = (props: IconProps) => <Svg {...props}>
  <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
</Svg>;

export const Warning = (props: IconProps) => <Svg {...props}>
  <path d="M12 4.5l8.5 15h-17zM12 10v4.5M12 17.2v.3" />
</Svg>;

export const Info = (props: IconProps) => <Svg {...props}>
  <circle cx="12" cy="12" r="8.5" />
  <path d="M12 11v5.5M12 7.8v.3" />
</Svg>;

export const Copy = (props: IconProps) => <Svg {...props}>
  <rect x="9" y="9" width="11" height="11" rx="2" />
  <path d="M15 6.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h.5" />
</Svg>;

export const Refresh = (props: IconProps) => <Svg {...props}>
  <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5V10h-5.5" />
</Svg>;

export const Print = (props: IconProps) => <Svg {...props}>
  <path d="M7 9V4h10v5M7 18H5.5A1.5 1.5 0 0 1 4 16.5V11a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5.5a1.5 1.5 0 0 1-1.5 1.5H17" />
  <rect x="7" y="14" width="10" height="6" rx="1" />
</Svg>;

export const Upload = (props: IconProps) => <Svg {...props}>
  <path d="M12 16V5M7.5 9.5L12 5l4.5 4.5M5 19h14" />
</Svg>;

export const Layers = (props: IconProps) => <Svg {...props}>
  <path d="M12 4l8 4.5-8 4.5-8-4.5zM4 13l8 4.5 8-4.5" />
</Svg>;

export const Bolt = (props: IconProps) => <Svg {...props}>
  <path d="M13 3L5.5 13.5H11L10 21l7.5-10.5H12z" />
</Svg>;
