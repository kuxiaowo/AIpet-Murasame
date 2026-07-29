#import <Cocoa/Cocoa.h>
#import <CoreGraphics/CoreGraphics.h>
#import <sys/file.h>
#import <fcntl.h>
#import <unistd.h>

@interface AIpetFullscreenPanel : NSPanel <NSTextViewDelegate>
@property(nonatomic, copy) NSString *imagePath;
@property(nonatomic, copy) NSString *statePath;
@property(nonatomic, copy) NSString *visibilityPath;
@property(nonatomic, copy) NSString *commandPath;
@property(nonatomic, strong) NSImageView *imageView;
@property(nonatomic, strong) NSTextView *inputView;
@property(nonatomic, strong) NSDate *imageDate;
@property(nonatomic) BOOL fullscreen;
@property(nonatomic) BOOL qtVisible;
@property(nonatomic) BOOL shown;
@property(nonatomic) BOOL inputMode;
@property(nonatomic) BOOL dragging;
@property(nonatomic) NSPoint dragOffset;
@end

@implementation AIpetFullscreenPanel
- (BOOL)canBecomeKeyWindow { return YES; }
- (BOOL)canBecomeMainWindow { return NO; }
- (void)mouseDown:(NSEvent *)event {
    if (event.modifierFlags & NSEventModifierFlagOption) {
        self.dragging = YES;
        self.dragOffset = event.locationInWindow;
    } else if (self.fullscreen && event.locationInWindow.y < self.frame.size.height * 0.38) {
        self.inputMode = YES;
        self.level = NSFloatingWindowLevel;
        self.inputView.hidden = NO;
        self.inputView.editable = YES;
        self.inputView.string = @"";
        [self makeKeyAndOrderFront:nil];
        [NSApp activateIgnoringOtherApps:YES];
        [self makeFirstResponder:self.inputView];
    }
}
- (void)otherMouseDown:(NSEvent *)event { self.dragging = YES; self.dragOffset = event.locationInWindow; }
- (void)mouseDragged:(NSEvent *)event {
    if (!self.dragging) return;
    NSPoint mouse = NSEvent.mouseLocation;
    [self setFrameOrigin:NSMakePoint(mouse.x - self.dragOffset.x, mouse.y - self.dragOffset.y)];
}
- (void)mouseUp:(NSEvent *)event { self.dragging = NO; }
- (void)otherMouseUp:(NSEvent *)event { self.dragging = NO; }
- (BOOL)textView:(NSTextView *)view doCommandBySelector:(SEL)selector {
    if (selector == @selector(insertNewline:)) {
        NSString *text = [view.string stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet];
        if (text.length) [text writeToFile:self.commandPath atomically:YES encoding:NSUTF8StringEncoding error:nil];
        self.inputMode = NO;
        self.level = 101;
        view.editable = NO;
        view.hidden = YES;
        [self makeFirstResponder:nil];
        return YES;
    }
    if (selector == @selector(cancelOperation:)) {
        self.inputMode = NO;
        self.level = 101;
        view.editable = NO;
        view.hidden = YES;
        [self makeFirstResponder:nil];
        return YES;
    }
    return NO;
}
@end

static BOOL frontmostAppHasFullscreenWindow(void) {
    NSRunningApplication *frontmost = NSWorkspace.sharedWorkspace.frontmostApplication;
    if (!frontmost || frontmost.processIdentifier == getpid()) return NO;
    NSArray *windows = CFBridgingRelease(CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements, kCGNullWindowID));
    NSRect screen = NSScreen.mainScreen.frame;
    for (NSDictionary *info in windows) {
        if ([info[(id)kCGWindowOwnerPID] intValue] != frontmost.processIdentifier) continue;
        CGRect rect;
        if (CGRectMakeWithDictionaryRepresentation((__bridge CFDictionaryRef)info[(id)kCGWindowBounds], &rect) && rect.size.width >= screen.size.width * .9 && rect.size.height >= screen.size.height * .9) return YES;
    }
    return NO;
}

static void refresh(AIpetFullscreenPanel *panel) {
    NSDictionary *attributes = [[NSFileManager defaultManager] attributesOfItemAtPath:panel.imagePath error:nil];
    NSDate *date = attributes[NSFileModificationDate];
    if (date && (!panel.imageDate || [date compare:panel.imageDate] == NSOrderedDescending)) {
        NSImage *image = [[NSImage alloc] initWithContentsOfFile:panel.imagePath];
        if (image) { panel.imageView.image = image; panel.imageDate = date; }
    }
    NSString *visible = [NSString stringWithContentsOfFile:panel.visibilityPath encoding:NSUTF8StringEncoding error:nil];
    panel.qtVisible = visible.integerValue != 0;
    NSRunningApplication *frontmost = NSWorkspace.sharedWorkspace.frontmostApplication;
    BOOL fullscreen = frontmost.processIdentifier == getpid()
        ? panel.fullscreen
        : frontmostAppHasFullscreenWindow();
    if (fullscreen != panel.fullscreen) {
        panel.fullscreen = fullscreen;
        [(fullscreen ? @"1\n" : @"0\n") writeToFile:panel.statePath atomically:YES encoding:NSUTF8StringEncoding error:nil];
    }
    BOOL shouldShow = fullscreen && !panel.qtVisible;
    if (shouldShow == panel.shown) return;
    panel.shown = shouldShow;
    if (shouldShow) [panel orderFrontRegardless]; else [panel orderOut:nil];
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 5) return 2;
        NSString *imagePath = [NSString stringWithUTF8String:argv[1]];
        NSString *statePath = [NSString stringWithUTF8String:argv[2]];
        NSString *visibilityPath = [NSString stringWithUTF8String:argv[3]];
        NSString *commandPath = [NSString stringWithUTF8String:argv[4]];
        NSString *lockPath = [statePath stringByAppendingString:@".lock"];
        int lock = open(lockPath.UTF8String, O_CREAT | O_RDWR, 0600);
        if (lock < 0 || flock(lock, LOCK_EX | LOCK_NB)) return 0;
        NSImage *image = [[NSImage alloc] initWithContentsOfFile:imagePath];
        if (!image) return 1;
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
        NSSize size = image.size;
        NSRect frame = NSScreen.mainScreen.visibleFrame;
        AIpetFullscreenPanel *panel = [[AIpetFullscreenPanel alloc] initWithContentRect:NSMakeRect(NSMaxX(frame) - size.width - 24, NSMinY(frame) + 20, size.width, size.height) styleMask:NSWindowStyleMaskBorderless backing:NSBackingStoreBuffered defer:NO];
        panel.imagePath = imagePath; panel.statePath = statePath; panel.visibilityPath = visibilityPath; panel.commandPath = commandPath;
        panel.opaque = NO; panel.backgroundColor = NSColor.clearColor; panel.hasShadow = NO; panel.hidesOnDeactivate = NO; panel.floatingPanel = YES; panel.level = 101;
        panel.collectionBehavior = NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorCanJoinAllApplications | NSWindowCollectionBehaviorFullScreenAuxiliary | NSWindowCollectionBehaviorStationary;
        panel.imageView = [[NSImageView alloc] initWithFrame:panel.contentView.bounds];
        panel.imageView.image = image; panel.imageView.imageScaling = NSImageScaleProportionallyUpOrDown;
        [panel.contentView addSubview:panel.imageView];
        panel.inputView = [[NSTextView alloc] initWithFrame:NSMakeRect(18, size.height * .42, size.width - 36, size.height * .28)];
        panel.inputView.hidden = YES; panel.inputView.editable = NO; panel.inputView.delegate = panel; panel.inputView.drawsBackground = NO; panel.inputView.textColor = NSColor.whiteColor; panel.inputView.font = [NSFont systemFontOfSize:16];
        [panel.contentView addSubview:panel.inputView];
        [@"0\n" writeToFile:statePath atomically:YES encoding:NSUTF8StringEncoding error:nil];
        [NSTimer scheduledTimerWithTimeInterval:.1 repeats:YES block:^(NSTimer *timer) { refresh(panel); }];
        [NSApp run];
    }
}
