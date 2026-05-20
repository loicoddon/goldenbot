import Link from 'next/link';

export function LogoMark({ size = 32 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="drop-shadow-[0_0_10px_rgba(255,215,0,0.25)]"
      aria-hidden
    >
      <defs>
        <linearGradient id="goldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#FFF4B0" />
          <stop offset="40%" stopColor="#FFD700" />
          <stop offset="100%" stopColor="#B8860B" />
        </linearGradient>
        <linearGradient id="darkInner" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#131826" />
          <stop offset="100%" stopColor="#0B0F19" />
        </linearGradient>
      </defs>

      {/* Outer hex (gold) */}
      <path
        d="M20 2 L35 11 L35 29 L20 38 L5 29 L5 11 Z"
        fill="url(#goldGrad)"
      />

      {/* Inner dark cutout */}
      <path
        d="M20 6 L31 12.5 L31 27.5 L20 34 L9 27.5 L9 12.5 Z"
        fill="url(#darkInner)"
      />

      {/* Ascending chart line */}
      <polyline
        points="12,26 16,22 20,25 24,18 28,21"
        stroke="url(#goldGrad)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />

      {/* Glowing endpoint */}
      <circle cx="28" cy="21" r="1.8" fill="#FFE066">
        <animate
          attributeName="opacity"
          values="1;0.3;1"
          dur="2.5s"
          repeatCount="indefinite"
        />
      </circle>

      {/* Subtle inner highlight on top edge */}
      <path
        d="M20 2 L35 11"
        stroke="#FFF4B0"
        strokeWidth="0.5"
        opacity="0.7"
        fill="none"
      />
    </svg>
  );
}

export function Logo() {
  return (
    <Link
      href="/"
      className="group flex items-center gap-2.5 min-w-0 transition-transform active:scale-95"
    >
      <span className="transition-transform group-hover:rotate-[15deg] duration-300">
        <LogoMark size={32} />
      </span>
      <span className="flex flex-col leading-none min-w-0">
        <span className="font-extrabold text-base md:text-lg tracking-tight">
          <span className="bg-gradient-to-br from-yellow-100 via-gold to-yellow-700 bg-clip-text text-transparent">
            Golden
          </span>
          <span className="text-gray-100">Bot</span>
        </span>
        <span className="text-[9px] md:text-[10px] uppercase tracking-[0.18em] text-gray-500 mt-0.5">
          XAU·USD · AI
        </span>
      </span>
    </Link>
  );
}
