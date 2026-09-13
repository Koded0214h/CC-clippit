import Image from "next/image";
import Link from "next/link";

export function Brand() {
  return (
    <Link className="brand" href="/" aria-label="Clippit home">
      <Image
        src="/assets/clippit-mark.png"
        alt=""
        width={40}
        height={40}
        priority
      />
      <span>
        Clippit<sup>™</sup>
      </span>
    </Link>
  );
}
