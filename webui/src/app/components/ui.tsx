import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const Button = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'default' | 'outline' | 'ghost' | 'secondary' | 'danger' | 'success', size?: 'default' | 'sm' | 'xs' | 'icon' | 'icon-xs' }>(
  ({ className, variant = 'default', size = 'default', ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-sm text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground-muted disabled:pointer-events-none disabled:opacity-50",
          {
            'bg-info-strong text-foreground-strong shadow hover:bg-info': variant === 'default',
            'border border-border-mitas bg-surface/50 shadow-sm hover:bg-surface-elevated hover:text-foreground-strong': variant === 'outline',
            'hover:bg-surface-elevated hover:text-foreground-strong': variant === 'ghost',
            'bg-surface-elevated text-foreground-strong hover:bg-surface-elevated/70': variant === 'secondary',
            'bg-danger-subtle text-danger hover:bg-danger/30 hover:text-foreground-strong': variant === 'danger',
            'bg-success-subtle text-success hover:bg-success/30 hover:text-foreground-strong': variant === 'success',

            'h-8 px-3 py-1': size === 'default',
            'h-7 px-2 text-xs': size === 'sm',
            'h-6 px-1.5 text-[10px]': size === 'xs',
            'h-8 w-8': size === 'icon',
            'h-6 w-6': size === 'icon-xs',
          },
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export const Badge = ({ className, variant = 'default', ...props }: React.HTMLAttributes<HTMLDivElement> & { variant?: 'default' | 'outline' | 'secondary' | 'success' | 'warning' | 'danger' }) => (
  <div
    className={cn(
      "inline-flex items-center rounded-sm px-1.5 py-0.5 text-[10px] font-medium transition-colors focus:outline-none font-mono uppercase tracking-wider",
      {
        'border border-transparent bg-foreground-strong text-app-shell': variant === 'default',
        'border border-transparent bg-surface-elevated text-foreground-strong': variant === 'secondary',
        'text-foreground-default border border-border-mitas bg-surface/50': variant === 'outline',
        'border border-transparent bg-success-subtle text-success': variant === 'success',
        'border border-transparent bg-warning-subtle text-warning': variant === 'warning',
        'border border-transparent bg-danger-subtle text-danger': variant === 'danger',
      },
      className
    )}
    {...props}
  />
)

export const Tabs = TabsPrimitive.Root

export const TabsList = React.forwardRef<React.ElementRef<typeof TabsPrimitive.List>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(
  ({ className, ...props }, ref) => (
    <TabsPrimitive.List
      ref={ref}
      className={cn(
        "inline-flex items-center justify-start bg-app-shell text-foreground-muted overflow-x-auto no-scrollbar",
        className
      )}
      {...props}
    />
  )
)
TabsList.displayName = TabsPrimitive.List.displayName

export const TabsTrigger = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Trigger>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>>(
  ({ className, ...props }, ref) => (
    <TabsPrimitive.Trigger
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center whitespace-nowrap px-3 py-1.5 text-[11px] uppercase tracking-wider font-semibold transition-all focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-surface data-[state=active]:text-info data-[state=active]:border-b-2 data-[state=active]:border-info-strong border-b-2 border-transparent hover:bg-surface/50",
        className
      )}
      {...props}
    />
  )
)
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

export const TabsContent = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Content>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>>(
  ({ className, ...props }, ref) => (
    <TabsPrimitive.Content
      ref={ref}
      className={cn(
        "ring-offset-app-shell focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-foreground-muted",
        className
      )}
      {...props}
    />
  )
)
TabsContent.displayName = TabsPrimitive.Content.displayName

export const ScrollArea = React.forwardRef<React.ElementRef<typeof ScrollAreaPrimitive.Root>, React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root>>(
  ({ className, children, ...props }, ref) => (
    <ScrollAreaPrimitive.Root
      ref={ref}
      className={cn("relative overflow-hidden", className)}
      {...props}
    >
      <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]">
        {children}
      </ScrollAreaPrimitive.Viewport>
      <ScrollBar />
      <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
  )
)
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName

export const ScrollBar = React.forwardRef<React.ElementRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>, React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>>(
  ({ className, orientation = "vertical", ...props }, ref) => (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
      ref={ref}
      orientation={orientation}
      className={cn(
        "flex touch-none select-none transition-colors",
        orientation === "vertical" &&
          "h-full w-2 border-l border-l-transparent p-[1px]",
        orientation === "horizontal" &&
          "h-2 flex-col border-t border-t-transparent p-[1px]",
        className
      )}
      {...props}
    >
      <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-sm bg-border-mitas hover:bg-foreground-muted" />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
  )
)
ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName
