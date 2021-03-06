import logging
import re
import telegram

from telegram import InlineKeyboardMarkup
from telegram.ext import (Updater, Filters,
                          CommandHandler,
                          ConversationHandler,
                          CallbackQueryHandler,
                          MessageHandler, RegexHandler)

from tictactoe import board, console, gomokuboard, gomokuconsole
from tictactoe.tictactoe import get_reply, run_move
from matches_game import MatchesGame, ACTIVE_GAMES
from mytokens import *
from wolfram_api_client import ask
from joker import get_jokes
from filters import FilterJoke, FilterTranslate
from ya_translater import translate_this
from speech import speech_to_text

joke_filter = FilterJoke()
translate_filter = FilterTranslate()

COMMANDS = [
    ('/tictactoe', 'Tic-Tac-Toe 3X3'),
    ('/matches', 'Matches Game'),
    ('/solve', 'Solve math tasks. Example: /solve x^3=27'),
    ('Ask for a joke: ', '"Tell me a joke about ..."'),
    ('Ask for a translation: ', '"Translate ..."'),
    ('', 'You can use voice input function.'),
]

GAME_COMMANDS = ['play', 'run']
SOLVE_COMMANDS = ['estimate', 'solve', 'calculate', 'compute', 'quantify', 'assess', 'evaluate']
BOARDS = {3: board, 8: gomokuboard}
CONSOLS = {3: console, 8: gomokuconsole}


class Tbot:
    """
    Telegram bot with the following functionalities:
    - It is self-explanatory.
    - It can solve simple equations and math tasks (integrate, derive, …)
    - It can play “tic-tac-toe” and “matches”
    - It can play XO 5-in-a-row
    """

    def __init__(self):
        self.custom_kb = []
        self.updater = Updater(token=telegram_token)
        self.bot = self.updater.bot
        self.dispatcher = self.updater.dispatcher
        self.games = {}
        self.human = {}

    def start(self, bot, update):
        response = ['{} {}'.format(x, y) for x, y in COMMANDS]
        response.insert(0, 'Make Your Choice:')
        response = '\n'.join(response)
        bot.send_message(chat_id=update.message.chat_id, text=response)

    def plain_text_manager(self, bot, update):
        """ This function parses plain text messages and executes correspondent rules. """
        text = update.message.text.strip().lower()
        if re.search(r"(.*(play|run).*matches.*)", text, re.IGNORECASE) is not None:
            return self.matches(bot, update)
        elif re.search(r".*(play|run).*(tic.*tac.*toe.*|deductible.*)", text, re.IGNORECASE) is not None:
            return self.ttt_size(bot, update)
        elif 'joke' in text:
            about = text.split('joke')[-1].strip()
            update.message.reply_text("Oh, you want a joke {}. Let's see...".format(about))
            try:
                response = get_jokes(text)
            except Exception as e:
                response = str(e)
            update.message.reply_text(response)
        elif 'translate' in text:
            text = text.split('translate')[-1].strip()
            try:
                response = translate_this(text)
            except Exception as e:
                response = str(e)
            update.message.reply_text(response)
        else:
            text_list = text.split()
            for w in SOLVE_COMMANDS:
                if w in text_list:
                    text = text.split(w)[-1].strip()
                    self.solve(bot, update, text.split())
                    return -1
            update.message.reply_text('Did you say: \"' + text + '\"?')
        return -1

    def voice_handler(self, bot, update):
        """ Voice recognition """
        file = self.bot.getFile(update.message.voice.file_id)
        print("file_id: " + str(update.message.voice.file_id))
        text = speech_to_text(file)
        print(text)
        update.message.text = text
        return self.plain_text_manager(bot, update)

    def ttt(self, bot, update):
        """ Tictactoe start """
        bot.sendMessage(chat_id=update.message.chat_id, text='Choose board size: 3 or 8')
        return 2

    def ttt_size(self, bot, update):
        """ Tictactoe choose board size """
        board_size = update.message.text.strip()
        if board_size not in ['3', '8']:
            bot.sendMessage(chat_id=update.message.chat_id, text='Choose board size: 3 or 8!')
            return 2
        else:
            custom_kb = [['X'], ['O']]
            reply = telegram.ReplyKeyboardMarkup(custom_kb)
            bot.sendMessage(chat_id=update.message.chat_id, text='Choose your side:', reply_markup=reply)
            return int(board_size)

    def ttt3(self, bot, update):
        """ Tictactoe size 3 """
        self.ttt_helper(bot, update, board_size=3)
        return 7

    def ttt5(self, bot, update):
        """ Tictactoe size 8 """
        self.ttt_helper(bot, update, board_size=8)
        return 7

    def ttt_helper(self, bot, update, board_size):
        """ Tictactoe helper """
        _board = BOARDS[board_size]
        _console = CONSOLS[board_size]
        try:
            if update.message.text == "X":
                human_move = _board.State.X
            elif update.message.text == 'O':
                human_move = _board.State.O
        except:
            pass
        bot.send_message(chat_id=update.message.chat_id, text='Preparing...',
                         reply_markup=telegram.ReplyKeyboardRemove())
        reply = get_reply(board_size)
        self.games[update.message.chat_id] = [_console.Console(board_size), reply, human_move, board_size]
        reply = InlineKeyboardMarkup(self.games[update.message.chat_id][1])
        if human_move == _board.State.O:
            self.play_move(bot, update, update.message.chat_id)

        bot.send_message(chat_id=update.message.chat_id, text='Let\'s play, my dear opponent! ', reply_markup=reply)

    def tictac(self, bot, update):
        """ Tictactoe """
        id = update.callback_query.message.chat_id
        self.play_move(bot, update, id)
        if self.games[id][0].board.game_over:
            self.get_winner(bot, update, id)
            return -1
        self.play_move(bot, update, id)
        if self.games[id][0].board.game_over:
            self.get_winner(bot, update, id)
            return -1
        return 7

    def play_move(self, bot, update, id):
        """ Tictactoe """
        game = self.games[id]
        board_size = game[3]
        _board = BOARDS[board_size]
        mc = game[0].board.move_count
        if game[0].board.get_turn() == game[2]:
            self.get_player_move(bot, update, id)
        else:
            run_move(game)
        for i in range(board_size):
            for j in range(board_size):
                if game[0].board.board[i][j] == _board.State.X:
                    game[1][i][j] = telegram.InlineKeyboardButton("❌",
                                                                  callback_data=str(i * board_size + j))
                elif game[0].board.board[i][j] == _board.State.O:
                    game[1][i][j] = telegram.InlineKeyboardButton('⭕️',
                                                                  callback_data=str(i * board_size + j))
        reply = InlineKeyboardMarkup(game[1])
        if game[0].board.move_count == 1 and game[2] == _board.State.O:
            pass
        elif mc < game[0].board.move_count:
            bot.editMessageText(chat_id=update.callback_query.message.chat_id,
                                message_id=update.callback_query.message.message_id,
                                text='Let\'s play, my dear opponent! ',
                                reply_markup=reply)

    def get_player_move(self, bot, update, id):
        """ Tictactoe """
        game = self.games[id]
        move = int(update.callback_query.data)
        if not game[0].board.move(move):
            try:
                query = update.callback_query
                reply = InlineKeyboardMarkup(game[1])
                bot.editMessageText(chat_id=query.message.chat_id,
                                    message_id=query.message.message_id,
                                    text="Press on the blank box please",
                                    reply_markup=reply
                                    )
            except telegram.error.BadRequest:
                pass

    def get_winner(self, bot, update, id):
        """ Tictactoe """
        game = self.games[id]
        board_size = game[3]
        _board = BOARDS[board_size]
        winner = game[0].board.get_winner()
        if winner == _board.State.Blank:
            s = "The TicTacToe is a Draw."
        else:
            if board_size == 3:
                s = "Player " + str(winner.name) + " wins!"
            elif board_size == 8:
                if winner == self.games[id][2]:
                    s = "You won!"
                else:
                    s = "AI won!"
        s += "\nTo start a new game press please /tictactoe"
        query = update.callback_query
        reply = InlineKeyboardMarkup(game[1])
        bot.editMessageText(chat_id=query.message.chat_id,
                            message_id=query.message.message_id,
                            text=s,
                            reply_markup=reply
                            )
        del self.games[id]

    def solve(self, bot, update, args):
        """ Solve math tasks using Wolfram Alpha. """
        request = ' '.join(args)
        result = ask(request)
        if result is None:
            result = "I don't know!"
        bot.send_message(chat_id=update.message.chat_id, text=result)

    def matches(self, bot, update):
        """ Matches Game. """
        game = ACTIVE_GAMES.get(update.message.chat_id, None)
        if game is None:
            game = MatchesGame(chat_id=update.message.chat_id)
            ACTIVE_GAMES[update.message.chat_id] = game
        bot.send_message(chat_id=update.message.chat_id, text=game.RULES)
        bot.send_message(chat_id=update.message.chat_id, text='Do you want to make first move? (y/n)')
        return 1

    def exit(self, bot, update):
        """ Exit Matches Game. """
        try:
            del ACTIVE_GAMES[update.message.chat_id]
        except KeyError:
            pass
        response = "The game is finished."
        bot.send_message(chat_id=update.message.chat_id, text=response)
        return -1

    def move(self, bot, update):
        """ Handles Matches moves. """
        text = update.message.text.strip()
        game = ACTIVE_GAMES.get(update.message.chat_id, None)
        code = 1
        if game is not None:
            code, response = game.get_response(text)
            for r in response:
                bot.send_message(chat_id=update.message.chat_id, text=r)
        return code

    def handlers(self):
        self.dispatcher.add_handler(CommandHandler('start', self.start))
        self.dispatcher.add_handler(CommandHandler('help', self.start))
        self.dispatcher.add_handler(CommandHandler('solve', self.solve, pass_args=True))

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('matches', self.matches),
                          CommandHandler('tictactoe', self.ttt),
                          MessageHandler(Filters.voice, self.voice_handler),
                          MessageHandler(Filters.text, self.plain_text_manager)],
            states={1: [MessageHandler(Filters.text, self.move), CommandHandler('exit', self.exit)],
                    2: [MessageHandler(Filters.text, self.ttt_size)],
                    7: [CallbackQueryHandler(self.tictac)],
                    3: [MessageHandler(Filters.text, self.ttt3), CallbackQueryHandler(self.ttt3)],
                    8: [MessageHandler(Filters.text, self.ttt5), CallbackQueryHandler(self.ttt5)]
                    },
            fallbacks=[CommandHandler('start', self.start)]
        )

        self.dispatcher.add_handler(conv_handler)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    bot = Tbot()
    bot.handlers()
    bot.updater.start_polling()
    bot.updater.idle()
