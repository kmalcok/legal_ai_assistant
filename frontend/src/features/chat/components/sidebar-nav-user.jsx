"use client"

import {
  BadgeCheck,
  Bell,
  ChevronsUpDown,
  CreditCard,
  LogOut,
  Sparkles,
  LifeBuoy
} from "lucide-react"

import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar"

export function NavUser({
  user,
  userLabel,
  creditLabel,
  creditSummary,
  onOpenSupport,
  onOpenSettings,
  onLogout,
}) {
  const { isMobile } = useSidebar()
  const avatarFallback = userLabel ? userLabel.substring(0,2).toUpperCase() : "YG"

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8 rounded-lg">
                <AvatarFallback className="rounded-lg">{avatarFallback}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                {creditSummary ? (
                  <>
                    <span className="truncate font-medium">{userLabel || 'Kullanıcı'}</span>
                    <span className="truncate text-xs">{`Kredi: ${creditSummary.total || '-'} / ${creditSummary.available || '-'}`}</span>
                  </>
                ) : (
                  <>
                    <span className="truncate font-medium">{userLabel || 'Kullanıcı'}</span>
                    <span className="truncate text-xs">{creditLabel ? `Kredi: ${creditLabel}` : 'Kredi: -'}</span>
                  </>
                )}
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            side="top"
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarFallback className="rounded-lg">{avatarFallback}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  {creditSummary ? (
                    <>
                      <span className="truncate font-medium">{userLabel || 'Kullanıcı'}</span>
                      <span className="truncate text-xs">{`Kredi : ${creditSummary.total || '-'}/${creditSummary.available || '-'}`}</span>
                    </>
                  ) : (
                    <>
                      <span className="truncate font-medium">{userLabel || 'Kullanıcı'}</span>
                      <span className="truncate text-xs">{creditLabel ? `Kredi: ${creditLabel}` : 'Kredi: -'}</span>
                    </>
                  )}
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuGroup>
              <DropdownMenuItem onClick={onOpenSettings}>
                <BadgeCheck className="mr-2 h-4 w-4" />
                Ayarlar
              </DropdownMenuItem>
              <DropdownMenuItem onClick={onOpenSupport}>
                <LifeBuoy className="mr-2 h-4 w-4" />
                Destek
              </DropdownMenuItem>
            </DropdownMenuGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onLogout} className="text-destructive focus:bg-destructive/10">
              <LogOut className="mr-2 h-4 w-4" />
              Çıkış yap
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
