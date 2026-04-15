interface SourceChipProps {
  filename: string;
  onClick?: () => void;
  active?: boolean;
}

export function SourceChip({ filename, onClick, active }: SourceChipProps) {
  const Tag = onClick ? "button" : "span";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={`source-chip${active ? " source-chip-active" : ""}`}
    >
      {filename}
    </Tag>
  );
}
