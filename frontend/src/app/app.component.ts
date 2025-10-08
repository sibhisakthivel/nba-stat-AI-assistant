import { Component } from '@angular/core';
import { ChatService } from './services/chat.service';

interface GameEvidence {
  table: 'game_details';
  id: number;
  home_team: string;
  away_team: string;
  home_points: number;
  away_points: number;
  game_date: string;
  display_name: string;
  pinned?: boolean;
}

interface PlayerEvidence {
  table: 'player_box_scores';
  id: string;
  player_name: string;
  team: string;
  points: number;
  rebounds?: number;
  assists?: number;
  game_id: number;
  display_name: string;
  pinned?: boolean;
}

type Evidence = GameEvidence | PlayerEvidence;

interface Message {
  sender: 'user' | 'bot';
  text: string;
  evidence?: Evidence[];
}

interface Chat {
  title: string;
  messages: Message[];
  pinned?: boolean;
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  title = 'AI Engineering Sandbox';
  chats: Chat[] = [];
  currentChatIndex = 0;
  userInput = '';
  expandedEvidence: { [key: string]: boolean } = {};
  editingChatIndex: number | null = null;
  originalTitle: string = '';
  isLoading: boolean = false;
  isDarkMode: boolean = false;

  constructor(private chatService: ChatService) {
    // Initialize with one empty chat
    this.createNewChat();

    // Check for saved theme preference or default to light mode
    const savedTheme = localStorage.getItem('theme');
    this.isDarkMode = savedTheme === 'dark';
  }

  createNewChat(): void {
    const chatNumber = this.chats.length + 1;
    this.chats.push({
      title: `Chat ${chatNumber}`,
      messages: [],
      pinned: false
    });
    this.currentChatIndex = this.chats.length - 1;
    this.userInput = '';
  }

  switchChat(index: number): void {
    this.currentChatIndex = index;
    this.userInput = '';
  }

  getCurrentChat(): Chat | null {
    return this.chats[this.currentChatIndex] || null;
  }

  sendMessage(): void {
    const input = this.userInput.trim();
    if (!input || !this.getCurrentChat()) {
      return;
    }

    const currentChat = this.getCurrentChat()!;

    // Update chat title based on first message
    if (currentChat.messages.length === 0) {
      currentChat.title = input.substring(0, 30) + (input.length > 30 ? '...' : '');
    }

    currentChat.messages.push({ sender: 'user', text: input });
    this.userInput = '';

    // Show loading animation
    this.isLoading = true;

    this.chatService.sendMessage(input).subscribe({
      next: (res: any) => {
        this.isLoading = false;
        const reply = res?.answer ?? 'No Answer.';
        currentChat.messages.push({
          sender: 'bot',
          text: reply,
          evidence: res?.evidence || []
        });
      },
      error: () => {
        this.isLoading = false;
        currentChat.messages.push({ sender: 'bot', text: 'Error contacting server.' });
      }
    });
  }

  toggleEvidence(key: string): void {
    this.expandedEvidence[key] = !this.expandedEvidence[key];
  }

  startEditing(index: number, event: Event): void {
    event.stopPropagation();
    this.editingChatIndex = index;
    this.originalTitle = this.chats[index].title;

    // Focus the input after Angular renders it
    setTimeout(() => {
      const input = document.querySelector('.chat-title-input') as HTMLInputElement;
      if (input) {
        input.focus();
        input.select();
      }
    }, 0);
  }

  stopEditing(): void {
    if (this.editingChatIndex !== null) {
      // Title is already bound via ngModel, so just clear the editing state
      this.editingChatIndex = null;
    }
  }

  cancelEditing(index: number): void {
    if (this.editingChatIndex !== null) {
      this.chats[index].title = this.originalTitle;
      this.editingChatIndex = null;
    }
  }

  togglePin(index: number, event: Event): void {
    event.stopPropagation();
    this.chats[index].pinned = !this.chats[index].pinned;

    // Sort chats to move pinned ones to the top
    this.sortChats();

    // Update current chat index to track the moved chat
    const currentChat = this.getCurrentChat();
    if (currentChat) {
      this.currentChatIndex = this.chats.indexOf(currentChat);
    }
  }

  deleteChat(index: number, event: Event): void {
    event.stopPropagation();

    if (this.chats.length === 1) {
      // Can't delete the last chat, just clear it instead
      this.chats[0] = {
        title: 'Chat 1',
        messages: [],
        pinned: false
      };
      return;
    }

    // Delete without confirmation
    this.chats.splice(index, 1);

    // Adjust current chat index if needed
    if (this.currentChatIndex >= this.chats.length) {
      this.currentChatIndex = this.chats.length - 1;
    } else if (this.currentChatIndex > index) {
      this.currentChatIndex--;
    }
  }

  toggleEvidencePin(messageIndex: number, evidenceIndex: number, event: Event): void {
    event.stopPropagation();
    const currentChat = this.getCurrentChat();
    if (currentChat && currentChat.messages[messageIndex]?.evidence) {
      const evidence = currentChat.messages[messageIndex].evidence!;
      evidence[evidenceIndex].pinned = !evidence[evidenceIndex].pinned;

      // Sort evidence to move pinned ones to the top
      evidence.sort((a, b) => {
        if (a.pinned && !b.pinned) return -1;
        if (!a.pinned && b.pinned) return 1;
        return 0;
      });
    }
  }

  deleteEvidence(messageIndex: number, evidenceIndex: number, event: Event): void {
    event.stopPropagation();
    const currentChat = this.getCurrentChat();
    if (currentChat && currentChat.messages[messageIndex]?.evidence) {
      // Delete without confirmation
      currentChat.messages[messageIndex].evidence!.splice(evidenceIndex, 1);
    }
  }

  toggleTheme(): void {
    this.isDarkMode = !this.isDarkMode;
    localStorage.setItem('theme', this.isDarkMode ? 'dark' : 'light');
  }

  private sortChats(): void {
    this.chats.sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return 0;
    });
  }
}