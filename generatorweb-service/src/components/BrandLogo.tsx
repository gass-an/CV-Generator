import { cn } from "@/lib/utils";

type BrandLogoProps = {
  brand: "cv-generator" | "opt" | "iae";
  className?: string;
};

const logos = {
  "cv-generator": {
    src: "/logos/CV_Generator.png",
    alt: "CV-Generator",
    size: "h-14 w-14 sm:h-16 sm:w-16",
  },
  opt: {
    src: "/logos/OPT.png",
    alt: "OPT Nouvelle-Calédonie",
    size: "h-9 w-auto sm:h-10",
  },
  iae: {
    src: "/logos/IAE.png",
    alt: "IAE Nouvelle-Calédonie",
    size: "h-11 w-auto sm:h-12",
  },
} as const;

export function BrandLogo({ brand, className }: BrandLogoProps) {
  const logo = logos[brand];

  return (
    <img
      src={logo.src}
      alt={logo.alt}
      className={cn("shrink-0 object-contain", logo.size, className)}
    />
  );
}
