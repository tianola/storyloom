The kind of machine that answers your questions weighs more than a tonne and draws as much power as a hundred homes.
Ask it why your cat sounds like a carburettor, and watch what that monster does. A few words. A pause. A few more words.
It is the most powerful computer most of us will ever touch, and yet it writes like someone pecking at a keyboard.
So why does it stutter?
The obvious guess is that it is thinking hard, that every single word takes a staggering amount of maths.
Keep that guess in mind, because we are going to test it. The real answer explains nearly everything about the buildings behind artificial intelligence.
To see it, let's follow a single word of your question on its trip. The word cat.
Cat leaves your phone as a radio wave and reaches a mast down the street.
From there it travels as light, trapped inside a strand of glass thinner than a hair.
But how do you keep light inside a bent piece of glass?
In eighteen forty two, a Swiss physicist called Daniel Colladon showed the trick with a jet of water.
Light that hits the inside of the jet at a shallow angle cannot escape, so it follows the water as it curves.
Glass fibre does exactly the same thing, bouncing the light off its walls over and over.
In twenty seventeen, a team at Heriot Watt University in Edinburgh actually filmed it.
Their camera caught a pulse of light racing around a coil of fibre, loop after loop.
In glass, light covers about two hundred thousand kilometres every second.
A thousand kilometres of cable costs cat about five thousandths of a second.
So the trip is not the slow part. Hold on to that.
The light ends in a warehouse of computers, like the one built for OpenAI in Abilene, Texas.
And there cat runs into its first problem. The chips inside cannot read.
They only understand numbers, so your question has to be chopped into pieces first.
The way it gets chopped comes from an unlikely place.
In February nineteen ninety four, a programmer in Colorado Springs called Philip Gage wrote a magazine article about shrinking files.
His idea was simple. Find the pair of characters that appears most often, and replace it with a new symbol.
Then do it again, and again, until the file is small.
Two decades later, Rico Sennrich and his colleagues borrowed that trick to split words for translation software.
Common words end up as single pieces, rare ones as fragments, and every piece gets a number.
ChatGPT's tokenizer works the same way. In it, cat with a space in front is number nine thousand and fifty nine.
That number is a key. It unlocks a long list of other numbers, a kind of address for the meaning of the word.
On a map, two numbers say where something is.
Here every token gets thousands of them, so it sits somewhere in a space with thousands of directions.
Training arranges that space so that cat ends up near dog, and a long way from carburettor.
But cat is not done yet. Now comes the climb.
OpenAI does not say how big the models behind ChatGPT are.
But in twenty twenty five it published an open model built the same way, with the blueprint.
That model is made of about a hundred and seventeen billion numbers, called weights.
Nobody typed them in. Training tuned them, step by step, on trillions of tokens of text.
They are stacked in thirty six layers, like the floors of a tower, and cat has to climb every floor.
On each floor, cat looks back at every word before it and decides which ones matter. That step is called attention.
It is how the word it gets linked to the thing it refers to.
Then cat visits a crowd of smaller networks on that floor, called experts.
But it does not visit all of them. A small router sends it to just four out of a hundred and twenty eight.
So on the whole climb, cat only touches about five billion weights.
Each touch is a multiplication and an addition, so that is roughly ten billion operations for a single new word.
What comes out of the top floor is not a sentence. It is a score for every possible next piece.
The system picks one, usually a likely one, with a little randomness so it does not sound like a robot.
And then the whole climb starts again from the ground floor, for the next piece.
A long answer means hundreds of climbs, one after another.
Ten billion operations for every word. So that must be the stutter, right? The maths?
Actually, no. That guess is wrong. The arithmetic is the easy part.
To see what the real problem is, picture the chip as a factory.
The workers who do the multiplying sit at desks. The weights do not live with them.
They live in a warehouse next door, and for every new piece of the answer, they have to be trucked in.
All of the weights that cat touches, every time. For that open model, the load is about five gigabytes.
Now take a Blackwell chip from NVIDIA, the kind in that Texas warehouse.
Its workers can finish ten billion operations in about four millionths of a second.
Its memory can deliver about eight terabytes a second, which sounds enormous.
But watch the race. At that speed, the five gigabyte delivery takes more than six hundred millionths of a second.
The truck takes over a hundred times longer than the work.
So when the chip writes for just you, its workers sit idle more than ninety nine percent of the time.
That is the pause you see. Engineers call it being memory bound.
And none of this surprised the people who saw it coming.
In nineteen ninety four, two computer scientists at the University of Virginia, William Wulf and Sally McKee, wrote a short paper with a blunt title.
Hitting the Memory Wall.
Processors were getting faster much more quickly than memory, they pointed out, and the gap kept widening.
Sooner or later, they warned, every program would end up waiting for memory instead of computing. Cat's climb is exactly that case.
They were right, and the wall is not just about time. It is about energy.
Twenty years later, the Stanford engineer Mark Horowitz put numbers on it.
Fetching a number from a memory chip cost about a hundred and seventy times more energy than multiplying two numbers.
The distance is the cost. Every bit has to be pushed down a wire, and the longer the wire, the more it burns.
So the question for everyone building these machines became: how do you stop moving so much?
The first answer was to move the warehouse.
At AMD, a team led by Bryan Black had been working on it since two thousand eight.
Their problem was graphics memory. Its power use simply would not scale to what the next chips needed.
So instead of spreading memory chips around the board, they stacked them into towers.
Tiny wires run straight down through the silicon, connecting every floor of the tower at once.
Then they set the towers right beside the processor, on the same slab of silicon.
In June twenty fifteen, AMD's Fiji was the first graphics chip to ship with this stacked memory.
Today it is called high bandwidth memory, and every Blackwell chip carries its own towers of it.
The road from warehouse to factory is now as short as anyone can make it.
But there is a catch. Even on that short road, the truck still takes hundreds of times longer than the work.
So the second answer was to stop sending the truck for just one person.
Every conversation uses exactly the same weights.
So the system gathers many conversations together, and a single delivery carries cat along with everyone else's words.
The workers who would nap for you stay busy for a crowd. This is called batching.
Except batching has a problem of its own. Every conversation needs a scratchpad.
For every word you send or receive, the model keeps the notes it made during attention, so it never has to redo them.
Those notes grow with every word and every person, and they fill the memory up.
In twenty twenty three, Woosuk Kwon and his colleagues at Berkeley measured how badly.
In the serving systems of the time, as little as a fifth of that scratchpad memory held actual notes.
The rest was reserved just in case, or lost in gaps between conversations.
Their fix came from an old idea in operating systems. Cut memory into small pages and hand them out only when needed.
With almost nothing wasted, the same chips could handle two to four times as many requests.
A year earlier, Tri Dao and his colleagues had applied the same lesson inside attention itself.
Their method, called FlashAttention, keeps the work in a tiny fast memory on the chip, so less has to travel back and forth.
The third answer was to make the cargo lighter.
In that open model, most weights are stored in just over four bits each, instead of the usual sixteen.
Smaller numbers mean a lighter truck on every trip, and the whole model fits on a single chip.
But the biggest models do not fit on one chip, and a busy service needs thousands of them.
So the chips are wired together, and here the fight against distance gets physical.
This is NVIDIA's rack for Blackwell, a cabinet taller than a person that weighs more than a tonne.
It holds seventy two of those chips, along with thirty six Grace processors to manage them.
Behind them runs a spine of copper cables, more than three kilometres of it, linking every chip to every other.
NVIDIA says the rack acts like a single, massive GPU.
A model can be cut into slices and spread across it, so each chip only fetches its own slice of cat's climb.
Where does all that effort go in the end?
It turns into heat. One of these racks draws about a hundred and twenty kilowatts, about as much as a hundred American homes.
Air cannot carry that away, so liquid runs through metal plates pressed onto every chip.
The heat has to go somewhere, and many sites dump it into the sky through cooling towers.
A tower lets a small part of the water evaporate, and the evaporation pulls heat out of the rest.
That is where the water in the headlines goes.
Days after ChatGPT launched, its chief executive Sam Altman wrote that the compute costs were eye-watering.
How much does cat's trip actually cost, then?
In twenty twenty five, he put an average query at about a third of a watt hour, about what an oven uses in a second or so.
Tiny, for one question. But ChatGPT gets around two and a half billion prompts a day.
Together, that is a steady load of about thirty five megawatts, the power of roughly thirty thousand homes.
And yet that is a single service, in an industry that is still building.
Which brings us back to cat.
Light carried it through glass, a trick from a jet of water in eighteen forty two.
A file compression idea from a nineteen ninety four magazine turned it into a number.
It climbed a tower of weights that had to be trucked in, again and again, for every piece of the answer.
Stacked memory shortened the road, batching shared the truck, and smaller numbers lightened the load.
Every one of those inventions fights the same wall that two scientists described in nineteen ninety four.
Moving a number costs more than using it.
So the next time an answer appears a few words at a time, watch the rhythm.
That little stutter is not the machine thinking.
It is the machine waiting for the truck.
