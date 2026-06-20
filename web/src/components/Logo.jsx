// Land-View logo mark: a map-pin housing a leaf/yard motif.
export default function Logo({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <defs>
        <linearGradient id="lv-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#15803d" />
          <stop offset="1" stopColor="#0ea5e9" />
        </linearGradient>
      </defs>
      {/* pin */}
      <path d="M16 2c-6 0-10.5 4.5-10.5 10.4C5.5 20 16 30 16 30s10.5-10 10.5-17.6C26.5 6.5 22 2 16 2z"
        fill="url(#lv-g)" />
      {/* leaf */}
      <path d="M16 8c-3.6 0-6.4 2.6-6.4 6.4 3.8 0 6.4-2.7 6.4-6.4z" fill="#fff" opacity="0.95" />
      <path d="M16 8c3.6 0 6.4 2.6 6.4 6.4-3.8 0-6.4-2.7-6.4-6.4z" fill="#fff" opacity="0.78" />
      <line x1="16" y1="9" x2="16" y2="18" stroke="#15803d" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}
