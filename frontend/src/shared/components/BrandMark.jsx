import React from 'react';
import { Scale } from 'lucide-react';
import { cn } from '@/lib/utils';

export function BrandMark({ className, iconClassName, textClassName, light = false }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className={cn(
        "w-9 h-9 rounded-xl flex items-center justify-center transition-transform hover:rotate-3",
        light ? "bg-white text-slate-900 shadow-xl shadow-white/10" : "bg-slate-900 text-white shadow-xl shadow-slate-900/10",
        iconClassName
      )}>
        <Scale size={20} strokeWidth={2.5} />
      </div>
      <span className={cn(
        "text-xl font-black tracking-widest uppercase",
        light ? "text-white" : "text-slate-900",
        textClassName
      )}>
        YARGUCU
      </span>
    </div>
  );
}
